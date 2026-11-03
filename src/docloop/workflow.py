"""执行控制中心：持久化 LangGraph、审批暂停、独立验证和审查路由。"""
import json
import re
import sqlite3
import subprocess
import time
from uuid import uuid4
from dataclasses import asdict
from pathlib import Path
from typing import TypedDict
import yaml
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt
from .adapters import DemoAdapter
from .contracts import transition, TaskContext
from .evidence import archive_change, normalize_evidence, validate_evidence
from .governance import GateError, Governance, write_json
from .reliability import Blocked, Limits, Reliability, classify_error, fingerprint
from .project import read_yaml, route_skills, select_context
from .execution_lock import run_lock
from .skill_runtime import SkillRegistry


class RunState(TypedDict, total=False):
    change_id: str
    status: str
    mode: str
    scenario: str
    acceptance_ids: list[str]
    history: list[str]
    commit: str
    error: str
    evidence: dict
    review: dict
    acceptance: dict
    archive: str
    task_context: dict


class Workflow:
    def __init__(self, root: Path, limits=None, *, instruction_root=None,
                 require_final_acceptance=False):
        self.root = Path(root).resolve()
        self.require_final_acceptance = bool(require_final_acceptance)
        self.instruction_root = Path(instruction_root).resolve() if instruction_root else self.root
        self.gov = Governance(self.root)
        config_path = self.instruction_root / '.docloop/project.yaml'
        self.project_config = read_yaml(config_path) if config_path.exists() else {}
        self.limits = limits or Limits(**self.project_config.get('limits', {}))
        self.reliability = Reliability(self.limits, clock=time.time)
        checkpoints = self.root / '.docloop/checkpoints'
        checkpoints.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(checkpoints / 'workflow.sqlite'), check_same_thread=False)
        graph = StateGraph(RunState)
        nodes = [('approval', self._approval), ('plan', self._plan),
                 ('implement', self._implement), ('verify', self._verify),
                 ('review', self._review)]
        if self.require_final_acceptance:
            nodes.append(('acceptance', self._acceptance))
        nodes.append(('archive', self._archive))
        for name, node in nodes:
            graph.add_node(name, self._guard(node))
        graph.add_edge(START, 'approval')
        chain = [('approval', 'plan'), ('plan', 'implement'), ('implement', 'verify'),
                 ('verify', 'review')]
        chain.append(('review', 'acceptance' if self.require_final_acceptance else 'archive'))
        if self.require_final_acceptance:
            chain.append(('acceptance', 'archive'))
        for current, following in chain:
            graph.add_conditional_edges(current, lambda state, nxt=following:
                                        END if state['status'] in {'blocked', 'failed', 'cancelled'} else nxt,
                                        {following: following, END: END})
        graph.add_edge('archive', END)
        self.graph = graph.compile(checkpointer=SqliteSaver(self.connection))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.connection.close()

    def config(self, change_id):
        self.gov.path(change_id)
        return {'configurable': {'thread_id': change_id}, 'recursion_limit': self.limits.graph_steps}

    def start(self, change_id, spec, scenario='success', mode=None, source='user-input'):
        mode = mode or self.project_config.get('mode', 'real')
        if scenario not in {'success', 'verification-failure'} or mode not in {'demo', 'real'}:
            raise GateError('Unknown mode or scenario')
        ids = list(dict.fromkeys(re.findall(r'\bAC-\d+\b', spec)))
        if not ids:
            raise GateError('Spec must declare acceptance IDs such as AC-001')
        self.gov.create(change_id, spec, source)
        context = TaskContext(change_id)
        if self.project_config:
            _, _, context.rules = select_context(self.instruction_root, context.domains)
            context.skills = route_skills(self.instruction_root, context.domains)
        context.validate()
        return self._invoke({'change_id': change_id, 'mode': mode, 'scenario': scenario,
                                  'status': 'draft', 'history': ['draft'], 'acceptance_ids': ids,
                                  'task_context': asdict(context)}, change_id)

    def _invoke(self, value, change_id):
        with run_lock(self.root, change_id):
            return self.graph.invoke(value, self.config(change_id))

    def status(self, change_id):
        values = self.graph.get_state(self.config(change_id)).values
        if not values:
            raise GateError('Run not found')
        return values

    def accept(self, change_id, approver, note=''):
        """真实 Run 的显式用户最终验收；demo/旧流程默认不进入此节点。"""
        snapshot = self.graph.get_state(self.config(change_id))
        if snapshot.values.get('status') != 'awaiting_acceptance' or snapshot.next != ('acceptance',):
            raise GateError('Run is not waiting for final user acceptance')
        if not approver.strip() or len(approver) > 120:
            raise GateError('Explicit final approver required')
        review = snapshot.values.get('review') or {}
        if review.get('status') != 'passed':
            raise GateError('Review must pass before final acceptance')
        return self._invoke(Command(resume={'decision': 'accepted', 'approver': approver.strip(),
                                            'note': note[:1000]}), change_id)

    def approve(self, change_id, expected_hash, approver):
        snapshot = self.graph.get_state(self.config(change_id))
        if snapshot.values.get('status') != 'draft' or snapshot.next != ('approval',):
            raise GateError('Run is not waiting for Spec approval')
        if expected_hash != self.gov.digest(change_id) or not approver.strip():
            raise GateError('Current Spec SHA256 and explicit approver required')
        return self._invoke(Command(resume={'sha256': expected_hash, 'approver': approver}), change_id)

    def resume(self, change_id):
        snapshot = self.graph.get_state(self.config(change_id))
        if not snapshot.next or snapshot.values.get('status') in {'draft', 'blocked', 'accepted', 'failed', 'cancelled'}:
            raise GateError('No resumable checkpoint; blocked runs require a new reviewed change')
        self.gov.assert_baseline(change_id)
        return self._invoke(None, change_id)

    def recover(self, change_id):
        """仅显式人工触发恢复，不自动唤醒，不重置预算或跳过失败节点。"""
        if self.status(change_id)['status'] != 'blocked':
            raise GateError('Only blocked runs can be explicitly recovered')
        self.gov.assert_baseline(change_id)
        path = self.root / '.docloop/recovery' / f'{change_id}.json'
        saved = json.loads(path.read_text(encoding='utf-8'))
        predecessors = {'_plan': 'approval', '_implement': 'plan', '_verify': 'implement',
                        '_review': 'verify', '_archive': 'review'}
        if saved.get('retry_node') not in predecessors:
            raise GateError('Recovery point requires new approval/change')
        restored = {key: saved[key] for key in RunState.__annotations__ if key in saved}
        restored['status'] = saved['resume_status']
        restored['error'] = ''
        with run_lock(self.root, change_id):
            self.graph.update_state(self.config(change_id), restored,
                                    as_node=predecessors[saved['retry_node']])
            return self.graph.invoke(None, self.config(change_id))

    def _load_budget(self, change_id):
        path = self.root / '.docloop/checkpoints' / f'{change_id}-budget.json'
        if path.exists():
            saved = json.loads(path.read_text(encoding='utf-8'))
            for key in ('usage', 'started', 'task_started', 'repairs', 'stalled',
                        'last_progress', 'fingerprints', 'failures'):
                setattr(self.reliability, key, saved[key])
        else:
            self.reliability = Reliability(self.limits, clock=time.time)

    def _save_budget(self, change_id):
        write_json(self.root / '.docloop/checkpoints' / f'{change_id}-budget.json', {
            key: getattr(self.reliability, key) for key in ('usage', 'started', 'task_started',
            'repairs', 'stalled', 'last_progress', 'fingerprints', 'failures')})

    def _guard(self, node):
        def guarded(state):
            try:
                if node.__name__ != '_approval':
                    self._load_budget(state['change_id'])
                    self.reliability.charge('graph_steps')
                    self.gov.assert_baseline(state['change_id'])
                if node.__name__ != '_acceptance':
                    self._prepare_agent_input(state, 'spec' if node.__name__ == '_approval' else node.__name__[1:])
                result = node(state)
                if node.__name__ != '_approval':
                    self._save_budget(state['change_id'])
                self._record(state['change_id'], node.__name__, result)
                return result
            except (GateError, Blocked, OSError, ValueError, sqlite3.Error) as error:
                record = {**state, 'status': 'blocked', 'error': str(error),
                          'retry_node': node.__name__, 'resume_status': state['status'],
                          'error_class': classify_error(error),
                          'retryable': classify_error(error) in {'timeout', 'network'},
                          'fingerprint': fingerprint(error), 'usage': self.reliability.usage,
                          'repair_history': self.reliability.fingerprints,
                          'next_step': 'Inspect evidence/environment; resolve blocker and create a reviewed change.'}
                sandbox = self.root / '.docloop/sessions' / state['change_id']
                if (sandbox / '.git').exists():
                    record['git_diff'] = subprocess.run(['git', 'diff', 'HEAD'], cwd=sandbox,
                        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10).stdout
                write_json(self.root / '.docloop/recovery' / f'{state["change_id"]}.json', record)
                self._save_budget(state['change_id'])
                self._record(state['change_id'], node.__name__, {'status': 'blocked', 'error': str(error)})
                return {'status': 'blocked', 'error': str(error)}
        return guarded

    def _prepare_agent_input(self, state, stage):
        if not self.project_config:
            return  # 无项目配置的最小测试/演示不宣称已加载项目 Skills。
        path = self.gov.path(state['change_id'])
        registry = SkillRegistry(self.instruction_root)
        packet = registry.build_agent_input(stage, state['task_context'],
                                             spec=(path / 'spec.md').read_text(encoding='utf-8'))
        snapshot = path / 'agent-inputs' / f'{stage}-{uuid4().hex}.json'
        write_json(snapshot, packet, exclusive=True)
        self.last_agent_input = packet
        trace = self.root / '.docloop/traces' / f'{state["change_id"]}.jsonl'
        trace.parent.mkdir(parents=True, exist_ok=True)
        with trace.open('a', encoding='utf-8') as stream:
            for skill in packet['skills']:
                stream.write(json.dumps({'event': 'skill.loaded', 'stage': stage, **skill,
                    'input_snapshot': snapshot.relative_to(self.root).as_posix(),
                    'input_sha256': packet['input_sha256'], 'model_invoked': False}, ensure_ascii=False) + '\n')

    def _record(self, change_id, stage, result):
        path = self.root / '.docloop/traces' / f'{change_id}.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'stage': stage, 'status': result.get('status'),
                                     'mode': self.status(change_id).get('mode'),
                                     'usage': dict(self.reliability.usage)}, ensure_ascii=False) + '\n')

    @staticmethod
    def _move(state, target, actor):
        transition(state['status'], target, actor)
        return {'status': target, 'history': [*state['history'], target]}

    def _approval(self, state):
        answer = interrupt({'message': 'Review Spec and approve its current SHA256',
                            'change_id': state['change_id'], 'sha256': self.gov.digest(state['change_id'])})
        baseline = self.gov.path(state['change_id']) / 'baseline/approval.json'
        if baseline.exists():
            # 崩溃重放只允许恢复同一份审批，不接受覆盖或新的审批身份。
            record = json.loads(baseline.read_text(encoding='utf-8'))
            if record['sha256'] != answer['sha256'] or record['approver'] != answer['approver']:
                raise GateError('Approval replay differs from original record')
            self.gov.assert_baseline(state['change_id'])
        else:
            self.gov.approve(state['change_id'], answer['sha256'], answer['approver'])
        self.gov.assert_baseline(state['change_id'])
        approved = (self.gov.path(state['change_id']) / 'baseline/spec.md').read_text(encoding='utf-8')
        ids = list(dict.fromkeys(re.findall(r'\bAC-\d+\b', approved)))
        if not ids:
            raise GateError('Approved Spec has no acceptance IDs')
        return {'status': 'draft', 'acceptance_ids': ids}

    def _plan(self, state):
        if state['mode'] != 'demo':
            raise Blocked('Real model/coding adapter is not configured; project-local Skill inputs prepared, no business implementation executed')
        path = self.gov.path(state['change_id'])
        rows = '\n'.join(f'| {ac} | TASK-001 | TC-{i:03} | V-{i:03} |'
                         for i, ac in enumerate(state['acceptance_ids'], 1))
        (path / 'tasks.md').write_text('# Controlled demo plan\n\n'
            'Mode: demo. No upstream Skill invocation claimed.\n\n'
            'TASK-001: write sandbox result.json, commit, independently parse value=42.\n', encoding='utf-8')
        (path / 'checklist.md').write_text('# Controlled demo checks\n\n'
            '| AC | Task | Test Case | Evidence |\n| --- | --- | --- | --- |\n' + rows, encoding='utf-8')
        return self._move(state, 'ready', 'orchestrator-agent')

    def _adapter(self, state):
        return DemoAdapter(self.root / '.docloop/sessions' / state['change_id'], self.reliability)

    def _implement(self, state):
        active = {**state, **self._move(state, 'in_progress', 'orchestrator-agent')}
        commit = self._adapter(state).implement(state['scenario'])
        return {**self._move(active, 'implemented', 'implement-agent'), 'commit': commit}

    def _verify(self, state):
        path = self.gov.path(state['change_id'])
        report = normalize_evidence(self._adapter(state).verify(state['acceptance_ids'], state['commit'], path / 'logs'))
        report['change_id'] = state['change_id']
        report['status'] = 'passed'
        (path / 'evidence.yaml').write_text(yaml.safe_dump({'verification': report},
                                                         allow_unicode=True), encoding='utf-8')
        validate_evidence(state['acceptance_ids'], report)
        return {**self._move(state, 'verified', 'verify-agent'), 'evidence': report}

    def _review(self, state):
        path = self.gov.path(state['change_id'])
        report = yaml.safe_load((path / 'evidence.yaml').read_text(encoding='utf-8'))['verification']
        validate_evidence(state['acceptance_ids'], report)
        for check in report['checks']:
            reference = (path / check['evidence']).resolve()
            if not reference.is_relative_to(path.resolve()) or not reference.is_file():
                raise GateError('Evidence reference missing or outside change scope')
        review = {'producer': 'review-agent', 'status': 'passed', 'mode': state['mode'],
                  'commit': state['commit'], 'missing_evidence': [],
                  'remaining_risks': ['Deterministic demo review; no semantic business-code review.']}
        (path / 'review.yaml').write_text(yaml.safe_dump(review, allow_unicode=True), encoding='utf-8')
        if self.require_final_acceptance:
            return {**self._move(state, 'awaiting_acceptance', 'review-agent'), 'review': review}
        return {'review': review}

    def _acceptance(self, state):
        answer = interrupt({'message': 'Explicit user final acceptance required',
                            'change_id': state['change_id'],
                            'commit': state.get('commit'),
                            'review': state.get('review', {})})
        if (not isinstance(answer, dict) or answer.get('decision') != 'accepted'
                or not str(answer.get('approver', '')).strip()):
            raise GateError('Explicit user final acceptance required')
        record = {'producer': 'user', 'status': 'accepted',
                  'approver': str(answer['approver']).strip(),
                  'note': str(answer.get('note', ''))[:1000],
                  'commit': state.get('commit')}
        return {**self._move(state, 'accepted', 'orchestrator-agent'), 'acceptance': record}

    def _archive(self, state):
        review = state.get('review', {})
        if review.get('status') != 'passed' or review.get('producer') != 'review-agent':
            raise GateError('Independent review required')
        validate_evidence(state['acceptance_ids'], state['evidence'])
        self._adapter(state).assert_commit(state['commit'])
        path = archive_change(self.root, state['change_id'], self.gov.path(state['change_id']))
        result = {'archive': str(path)}
        if state.get('status') != 'accepted':
            result.update(self._move(state, 'accepted', 'orchestrator-agent'))
        return result
