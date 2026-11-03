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
from .durable_io import save_json

EXECUTION_VERSION = 'managed-v2'
RESUMABLE = {'paused', 'interrupted', 'waiting_confirmation'}


class RunStopped(Exception):
    """协作式控制：保留图中当前未完成节点，恢复时重入。"""


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
    def __init__(self, store, preparation, plan_builder, analyzer=None):
        self.store, self.preparation, self.plan_builder = store, preparation, plan_builder
        self.analyzer = analyzer
        self._mutex, self._workers, self._active = Lock(), {}, {}
        self._closed = False
        # 服务全生命周期持有锁；恢复只发生在成功取得独占权之后。
        self._lease = run_lock(store.root, 'managed-run-service')
        self._lease.__enter__()
        try:
            store.recover_interrupted_runs()
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
            from .task_updates import pending_updates
            if pending_updates(self.store, project_id, spec_id):
                raise Conflict('此任务有补充资料待审阅，请处理新草稿或放弃批次后继续。')
            for previous in self.store.task_runs(project_id, spec_id, limit=None):
                if previous['mode'] == 'runtime' and previous['status'] in RESUMABLE:
                    return previous
            if project_id in self._active:
                run_id = self._active[project_id]
                run = self.status(project_id, run_id)
                if run['spec_id'] != spec_id:
                    raise Conflict('项目已有执行中的任务')
                return run
            if self._active:
                raise Conflict('当前服务已有执行准备Run；首版并发上限为1')
            run = self.store.start_run(project_id, spec_id, mode='runtime')
            folder = self.store.root / 'runs' / run['id']
            save_json(folder / 'run-input.json', {'version': EXECUTION_VERSION,
                'spec_hash': sha256(self.store.approved_bytes(project_id, spec_id)),
                'project_id': project_id, 'spec_id': spec_id, 'mode': 'runtime',
                'repository': self.preparation.binding(project_id) if hasattr(self.preparation, 'binding') else None})
            self._launch(run)
            return run

    def _launch(self, run):
        signal = Event()
        thread = Thread(target=self._work, args=(run['project_id'], run['spec_id'], run['id'], signal),
                        name='docloop-' + run['id'], daemon=False)
        self._active[run['project_id']] = run['id']
        self._workers[run['id']] = (thread, signal)
        thread.start()

    def start_analysis(self, project_id, spec_id, payload):
        with self._mutex:
            existing = self.store.task_runs(project_id, spec_id, limit=None)
            if existing:
                return existing[0]
            if self._closed or self._active:
                raise Conflict('已有任务运行中，请先暂停或等待完成。')
            run = self.store.start_run(project_id, spec_id, mode='analysis')
            save_json(self.store.root / 'runs' / run['id'] / 'run-input.json', {
                'version': EXECUTION_VERSION, 'project_id': project_id, 'spec_id': spec_id,
                'mode': 'analysis', 'revision': self.store.spec(project_id, spec_id)['revision'], **payload})
            self._launch(run)
            return run

    def pause(self, project_id, run_id):
        return self._control(project_id, run_id, 'pause')

    def _control(self, project_id, run_id, command):
        with self._mutex:
            row = self.status(project_id, run_id)
            if row['mode'] not in {'runtime', 'analysis'}:
                raise Conflict('此运行不支持持久控制。')
            worker = self._workers.get(run_id)
            if row['status'] == 'in_progress':
                if row['result'].get('control') == 'cancel' and command != 'cancel':
                    if worker:
                        worker[1].set()
                    return row
                row = self.store.transition_run(project_id, run_id, ['in_progress'], 'in_progress',
                    {'control': command, 'cancel_requested': command == 'cancel',
                     'reason': {'pause': '正在保存进度并暂停', 'cancel': '正在取消', 'shutdown': '服务正在停止'}[command]})
                if worker:
                    worker[1].set()
            elif command == 'cancel' and row['status'] in RESUMABLE:
                row = self.store.transition_run(project_id, run_id, [row['status']], 'cancelled',
                    {'control': 'cancel', 'reason': '用户已取消；历史产物保留。'})
            return row

    def resume(self, project_id, run_id):
        with self._mutex:
            row = self.status(project_id, run_id)
            from .task_updates import pending_updates
            if pending_updates(self.store, project_id, row['spec_id']):
                raise Conflict('此任务有补充资料待处理，不能继续使用旧输入。')
            if run_id in self._workers:
                return row
            allowed = {'paused', 'interrupted'} | ({'blocked'} if row['mode'] == 'analysis' else set())
            if self._closed or self._active or row['status'] not in allowed:
                raise Conflict('当前状态不能继续，或已有任务执行中。')
            folder = self.store.root / 'runs' / run_id
            try:
                saved = json.loads((folder / 'run-input.json').read_text(encoding='utf-8'))
            except (OSError, ValueError):
                raise Conflict('运行输入缺失或损坏，不能安全恢复。') from None
            if (saved.get('version') != EXECUTION_VERSION or saved.get('project_id') != project_id
                    or saved.get('spec_id') != row['spec_id']):
                raise Conflict('执行版本或归属不兼容，不能安全恢复。')
            if row['mode'] == 'runtime' and saved.get('spec_hash') != sha256(self.store.approved_bytes(project_id, row['spec_id'])):
                raise Conflict('审批输入已变化，不能恢复原运行。')
            if row['mode'] == 'runtime' and hasattr(self.preparation, 'binding') and saved.get('repository') != self.preparation.binding(project_id):
                raise Conflict('仓库登记或代码基线已变化，不能恢复原运行。')
            if not (folder / 'checkpoint.sqlite').is_file():
                raise Conflict('检查点缺失，不能安全恢复。')
            row = self.store.transition_run(project_id, run_id, [row['status']], 'in_progress',
                {'control': None, 'cancel_requested': False, 'reason': '从保存步骤继续'})
            self._launch(row)
            return row

    def status(self, project_id, run_id):
        # 归属由 DB 过滤，绝不根据调用方传入 run_id 直接拼路径。
        return self.store.run(project_id, run_id)

    def cancel(self, project_id, run_id):
        return self._control(project_id, run_id, 'cancel')

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
            folder.mkdir(parents=True, exist_ok=True)
            result = self._invoke(pid, sid, rid, signal, folder)
        except Exception as error:
            # 不把异常文本带出的模型返回、认证信息当作可公开运行结果。
            result = self._result('blocked', '准备失败：' + type(error).__name__)
        try:
            with self._mutex:
                if signal.is_set():
                    command = self.status(pid, rid)['result'].get('control')
                    status = {'pause': 'paused', 'shutdown': 'interrupted'}.get(command, 'cancelled')
                    result = self._result(status, {'paused': '已保存进度，可继续',
                        'interrupted': '服务中断；可从保存步骤恢复', 'cancelled': '用户已取消；历史产物保留'}[status])
                result['mode'] = self.status(pid, rid)['mode']
                changes = folder / '.docloop/changes' / rid
                try:
                    save_json(changes / 'run-summary.json', result)
                except OSError:
                    result = self._result(result['status'], '准备材料保存失败；请检查本地目录')
                self.store.finish_run(pid, rid, result)
        finally:
            with self._mutex:
                self._active.pop(pid, None)
                self._workers.pop(rid, None)

    def cancel_all(self):
        for pid, rid in list(self._active.items()):
            self._control(pid, rid, 'shutdown')

    def _invoke(self, pid, sid, rid, signal, folder):
        if self.status(pid, rid)['mode'] == 'analysis':
            return self._analyze(pid, sid, rid, signal, folder)
        changes = folder / '.docloop/changes' / rid
        trace = folder / '.docloop/traces' / (rid + '.jsonl')
        def check():
            if signal.is_set():
                raise RunStopped()
        def record(stage, status):
            trace.parent.mkdir(parents=True, exist_ok=True)
            with trace.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'stage': 'runtime.' + stage, 'status': status,
                    'mode': 'runtime', 'business_code_execution': False}) + '\n')

        def approval(state):
            check()
            raw = self.store.approved_bytes(pid, sid)
            (folder / 'approved-spec.md').write_bytes(raw)
            gov = Governance(folder)
            if not (changes / 'spec.md').exists():
                gov.create(rid, raw.decode('utf-8'), source=f'database-spec:{sid}')
            spec = self.store.spec(pid, sid)
            if not (changes / 'baseline/approval.json').exists():
                gov.approve(rid, sha256(raw), spec['approved_by'])
            # 复制原审批凭据，不把本次运行的快照误记为一次新的用户审批。
            write_json(changes / 'baseline/approval.json', self.store.approval_record(pid, sid))
            record('approval', 'passed')
            return {'status': 'in_progress'}

        def plan(state):
            check()
            raw = self.store.approved_bytes(pid, sid)
            record('plan', 'in_progress')
            cached = folder / 'plan.json'
            value = json.loads(cached.read_text(encoding='utf-8')) if cached.is_file() else self.plan_builder(raw.decode('utf-8'), signal, rid)
            value = validate_plan(value, raw.decode('utf-8'))
            # 取消不发布迟到结果；暂停允许保存已经完整返回的计划，避免继续时重复推理。
            if signal.is_set() and self.status(pid, rid)['result'].get('control') == 'cancel':
                raise RunStopped()
            save_json(cached, value)
            save_json(changes / 'plan.json', value)
            task_text = '# 执行计划（尚未执行）\n\n' + '\n\n'.join(
                f'## {t["id"]}\n{t["description"]}\nAC: {", ".join(t["acceptance_ids"])}' for t in value['tasks'])
            test_text = '# 验收测试计划（不是测试结果）\n\n' + '\n\n'.join(
                f'## {t["id"]}\n{t["description"]}\n预期：{t["expected"]}\nTASK: {", ".join(t["task_ids"])}\nAC: {", ".join(t["acceptance_ids"])}'
                for t in value['test_cases'])
            (changes / 'tasks.md').write_text(task_text, encoding='utf-8')
            (changes / 'checkList.md').write_text(test_text, encoding='utf-8')
            record('plan', 'planned')
            check()
            return {'plan': value}

        def prepare(state):
            check()
            self.store.approved_bytes(pid, sid)
            saved = json.loads((folder / 'run-input.json').read_text(encoding='utf-8'))
            if hasattr(self.preparation, 'binding') and saved.get('repository') != self.preparation.binding(pid):
                raise Conflict('仓库绑定变化，停止旧计划。')
            receipt = changes / 'preparation.json'
            if receipt.is_file():
                value = json.loads(receipt.read_text(encoding='utf-8'))
            else:
                with cancellation_scope(signal):
                    value = self.preparation.prepare(pid, sid)
                save_json(receipt, value)
            check()
            record('prepare', 'blocked')
            return {'preparation': value, 'status': 'blocked',
                    'reason': '执行准备已结束；真实编码执行及权限门禁未启用'}

        graph = StateGraph(State)
        for name, node in [('approval', approval), ('plan', plan), ('prepare', prepare)]:
            graph.add_node(name, node)
        graph.add_edge(START, 'approval')
        for current, following in [('approval', 'plan'), ('plan', 'prepare')]:
            graph.add_edge(current, following)
        graph.add_edge('prepare', END)
        with closing(sqlite3.connect(folder / 'checkpoint.sqlite', check_same_thread=False)) as connection:
            app = graph.compile(checkpointer=SqliteSaver(connection))
            config = {'configurable': {'thread_id': rid}}
            snapshot = app.get_state(config)
            if snapshot.values and not snapshot.next:
                result = snapshot.values
            else:
                result = app.invoke(None if snapshot.values else {'status': 'in_progress'}, config)
        return self._result(result.get('status', 'blocked'), result.get('reason', '取消请求已处理'),
                            preparation=result.get('preparation', {}))

    def _analyze(self, pid, sid, rid, signal, folder):
        def analyze(state):
            if signal.is_set():
                raise RunStopped()
            saved = json.loads((folder / 'run-input.json').read_text(encoding='utf-8'))
            self.analyzer(pid, sid, saved, signal, folder)
            if signal.is_set():
                raise RunStopped()
            return {'status': 'succeeded', 'reason': '需求分析已保存，等待用户审阅审批。'}
        graph = StateGraph(State)
        graph.add_node('analyze', analyze)
        graph.add_edge(START, 'analyze')
        graph.add_edge('analyze', END)
        with closing(sqlite3.connect(folder / 'checkpoint.sqlite', check_same_thread=False)) as connection:
            app = graph.compile(checkpointer=SqliteSaver(connection))
            config = {'configurable': {'thread_id': rid}}
            snapshot = app.get_state(config)
            result = snapshot.values if snapshot.values and not snapshot.next else app.invoke(
                None if snapshot.values else {'status': 'in_progress'}, config)
        return {**self._result(result['status'], result['reason']), 'mode': 'analysis'}

    def close(self):
        self.cancel_all()
        with self._mutex:
            if self._closed:
                return
            self._closed = True
            workers = list(self._workers.values())
        for thread, _ in workers:
            thread.join()
        self._lease.__exit__(None, None, None)
