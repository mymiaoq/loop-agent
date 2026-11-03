"""可取消的LangGraph执行准备；生成计划，不运行生成代码。"""
import json
import re
import sqlite3
from contextlib import closing
from threading import Event, Lock, Thread
from typing import TypedDict
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END
from docloop.execution_lock import run_lock
from docloop.workbench_store import Conflict, NotFound
from .governance import Governance, sha256, write_json
from .worktree_runtime import cancellation_scope


class State(TypedDict, total=False):
    status: str
    plan: dict
    preparation: dict
    reason: str


def validate_plan(plan, spec):
    """计划必须覆盖批准 Spec 全部 AC，并提供有内容的 TASK 与 TC。"""
    acs = set(re.findall(r'\bAC-\d+\b', spec))
    if not isinstance(plan, dict) or not acs:
        raise ValueError('缺少有效计划或 AC')
    tasks, cases = plan.get('tasks', []), plan.get('test_cases', [])
    if not isinstance(tasks, list) or not isinstance(cases, list) or len(tasks) > 100 or len(cases) > 500:
        raise ValueError('计划结构或数量无效')
    task_ids, covered, tested = set(), set(), set()
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError('任务结构无效')
        ids = set(task.get('acceptance_ids', []))
        if (not re.fullmatch(r'TASK-\d+', task.get('id', '')) or
                task['id'] in task_ids or not task.get('description', '').strip() or
                not ids or not ids <= acs):
            raise ValueError('TASK 内容或 AC 映射无效')
        task_ids.add(task['id'])
        covered.update(ids)
    case_ids, tested_tasks = set(), set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError('测试计划结构无效')
        ids = set(case.get('acceptance_ids', []))
        if (not re.fullmatch(r'TC-\d+', case.get('id', '')) or case['id'] in case_ids or
                not case.get('description', '').strip() or not case.get('expected', '').strip() or
                not ids or not ids <= acs or not case.get('task_ids') or
                not set(case['task_ids']) <= task_ids):
            raise ValueError('TC 内容或 TASK/AC 映射无效')
        case_ids.add(case['id'])
        tested_tasks.update(case['task_ids'])
        tested.update(ids)
        linked = set().union(*(set(t['acceptance_ids']) for t in tasks if t['id'] in case['task_ids']))
        if not ids <= linked:
            raise ValueError('TC对应AC与关联TASK不一致')
    if covered != acs or tested != acs or tested_tasks != task_ids:
        raise ValueError('计划没有完整覆盖批准 AC')
    return plan


class ManagedRuns:
    def __init__(self, store, preparation, plan_builder):
        self.store, self.preparation, self.plan_builder = store, preparation, plan_builder
        self._mutex, self._workers, self._active = Lock(), {}, {}
        self._closed = False
        # 服务全生命周期持有锁；恢复只发生在成功取得独占权之后。
        self._lease = run_lock(store.root, 'managed-run-service')
        self._lease.__enter__()
        try:
            for run in store.pending_runs('runtime'):
                store.finish_run(run['project_id'], run['id'], self._result('blocked', '服务中断；未自动重跑'))
        except BaseException:
            self._lease.__exit__(None, None, None)
            raise

    @staticmethod
    def _result(status, reason, **details):
        return dict(status=status, reason=reason, mode='runtime',
                    real_business_acceptance=False, business_code_execution=False, **details)

    def start(self, project_id, spec_id):
        with self._mutex:
            if self._closed:
                raise Conflict('服务已关闭')
            self.store.approved_bytes(project_id, spec_id)
            if project_id in self._active:
                run_id = self._active[project_id]
                run = self.status(project_id, run_id)
                if run['spec_id'] != spec_id:
                    raise Conflict('项目已有执行中的任务')
                return run
            if self._active:
                raise Conflict('当前服务已有执行准备Run；首版并发上限为1')
            run = self.store.start_run(project_id, spec_id, mode='runtime')
            signal = Event()
            thread = Thread(target=self._work, args=(project_id, spec_id, run['id'], signal),
                            name='docloop-' + run['id'], daemon=False)
            self._active[project_id] = run['id']
            self._workers[run['id']] = (thread, signal)
            thread.start()
            return run

    def status(self, project_id, run_id):
        # 归属由 DB 过滤，绝不根据调用方传入 run_id 直接拼路径。
        return self.store.run(project_id, run_id)

    def cancel(self, project_id, run_id):
        with self._mutex:
            row = self.status(project_id, run_id)
            if row['mode'] != 'runtime':
                raise Conflict('此入口仅取消执行准备Run')
            worker = self._workers.get(run_id)
            if row['status'] == 'in_progress' and worker:
                if not worker[1].is_set():
                    self.store.request_cancel(project_id, run_id)
                worker[1].set()
            return self.status(project_id, run_id)

    def wait(self, project_id, run_id, timeout=None):
        self.status(project_id, run_id)
        with self._mutex:
            worker = self._workers.get(run_id)
        if worker:
            worker[0].join(timeout)
        return self.status(project_id, run_id)

    def _work(self, pid, sid, rid, signal):
        folder = self.store.root / 'runs' / rid
        try:
            folder.mkdir(parents=True, exist_ok=False)
            result = self._invoke(pid, sid, rid, signal, folder)
        except Exception as error:
            # 不把异常文本带出的模型返回、认证信息当作可公开运行结果。
            result = self._result('cancelled' if signal.is_set() else 'blocked',
                                  '取消请求已处理' if signal.is_set() else '准备失败：' + type(error).__name__)
        try:
            with self._mutex:
                if signal.is_set():
                    result = self._result('cancelled', '取消请求已处理；未进行业务验收')
                changes = folder / '.docloop/changes' / rid
                try:
                    write_json(changes / 'run-summary.json', result)
                except OSError:
                    result = self._result(result['status'], '准备材料保存失败；请检查本地目录')
                self.store.finish_run(pid, rid, result)
        finally:
            with self._mutex:
                self._active.pop(pid, None)
                self._workers.pop(rid, None)

    def cancel_all(self):
        with self._mutex:
            for _, signal in self._workers.values():
                signal.set()

    def _invoke(self, pid, sid, rid, signal, folder):
        changes = folder / '.docloop/changes' / rid
        trace = folder / '.docloop/traces' / (rid + '.jsonl')
        def record(stage, status):
            trace.parent.mkdir(parents=True, exist_ok=True)
            with trace.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'stage': 'runtime.' + stage, 'status': status,
                    'mode': 'runtime', 'business_code_execution': False}) + '\n')

        def approval(state):
            raw = self.store.approved_bytes(pid, sid)
            (folder / 'approved-spec.md').write_bytes(raw)
            gov = Governance(folder)
            gov.create(rid, raw.decode('utf-8'), source=f'database-spec:{sid}')
            spec = self.store.spec(pid, sid)
            gov.approve(rid, sha256(raw), spec['approved_by'])
            # 复制原审批凭据，不把本次运行的快照误记为一次新的用户审批。
            write_json(changes / 'baseline/approval.json', self.store.approval_record(pid, sid))
            record('approval', 'passed')
            return {'status': 'in_progress'}

        def plan(state):
            if signal.is_set():
                return {'status': 'cancelled'}
            raw = self.store.approved_bytes(pid, sid)
            record('plan', 'in_progress')
            value = self.plan_builder(raw.decode('utf-8'), signal, rid)
            if signal.is_set():
                return {'status': 'cancelled'}
            value = validate_plan(value, raw.decode('utf-8'))
            (folder / 'plan.json').write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
            write_json(changes / 'plan.json', value)
            task_text = '# 执行计划（尚未执行）\n\n' + '\n\n'.join(
                f'## {t["id"]}\n{t["description"]}\nAC: {", ".join(t["acceptance_ids"])}' for t in value['tasks'])
            test_text = '# 验收测试计划（不是测试结果）\n\n' + '\n\n'.join(
                f'## {t["id"]}\n{t["description"]}\n预期：{t["expected"]}\nTASK: {", ".join(t["task_ids"])}\nAC: {", ".join(t["acceptance_ids"])}'
                for t in value['test_cases'])
            (changes / 'tasks.md').write_text(task_text, encoding='utf-8')
            (changes / 'checkList.md').write_text(test_text, encoding='utf-8')
            record('plan', 'planned')
            return {'plan': value}

        def prepare(state):
            if signal.is_set():
                return {'status': 'cancelled'}
            self.store.approved_bytes(pid, sid)
            with cancellation_scope(signal):
                value = self.preparation.prepare(pid, sid)
            write_json(changes / 'preparation.json', value)
            record('prepare', 'blocked')
            return {'preparation': value, 'status': 'blocked',
                    'reason': '执行准备已结束；真实编码执行及权限门禁未启用'}

        graph = StateGraph(State)
        for name, node in [('approval', approval), ('plan', plan), ('prepare', prepare)]:
            graph.add_node(name, node)
        graph.add_edge(START, 'approval')
        for current, following in [('approval', 'plan'), ('plan', 'prepare')]:
            graph.add_conditional_edges(current, lambda state, nxt=following:
                END if signal.is_set() or state['status'] == 'cancelled' else nxt)
        graph.add_edge('prepare', END)
        with closing(sqlite3.connect(folder / 'checkpoint.sqlite', check_same_thread=False)) as connection:
            app = graph.compile(checkpointer=SqliteSaver(connection))
            result = app.invoke({'status': 'in_progress'}, {'configurable': {'thread_id': rid}})
        return self._result(result.get('status', 'blocked'), result.get('reason', '取消请求已处理'),
                            preparation=result.get('preparation', {}))

    def close(self):
        with self._mutex:
            if self._closed:
                return
            self._closed = True
            workers = list(self._workers.values())
            for _, signal in workers:
                signal.set()
        for thread, _ in workers:
            thread.join()
        self._lease.__exit__(None, None, None)
