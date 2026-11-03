"""V2 状态分层与旧值兼容映射；Task/Worker 只是运行元数据。"""
import re
from .governance import GateError

SPEC_STATUSES = {'draft', 'approved', 'superseded'}
RUN_STATUSES = {'draft', 'ready', 'in_progress', 'implemented', 'verified',
                'reviewed', 'awaiting_acceptance', 'accepted', 'blocked',
                'failed', 'cancelled', 'needs_input'}
TASK_STATUSES = {'pending', 'ready', 'claimed', 'running', 'implemented',
                 'verified', 'failed', 'blocked', 'cancelled'}
WORKER_STATUSES = {'starting', 'ready', 'busy', 'draining', 'stopped', 'lost'}
EVIDENCE_RESULTS = {'passed', 'failed', 'blocked', 'not_run'}
REVIEW_RESULTS = {'approved', 'rejected', 'needs_attention'}

SPEC_ALIASES = {'active': 'approved'}
RUN_ALIASES = {'planned': 'ready'}
REVIEW_TO_RUN = {'approved': 'awaiting_acceptance', 'rejected': 'implemented',
                 'needs_attention': 'needs_input'}
RUN_TO_TASK = {'draft': 'pending', 'ready': 'ready', 'in_progress': 'running',
               'implemented': 'implemented', 'verified': 'verified',
               'reviewed': 'verified', 'awaiting_acceptance': 'verified',
               'accepted': 'verified', 'blocked': 'blocked', 'failed': 'failed',
               'cancelled': 'cancelled', 'needs_input': 'ready'}

_DOMAINS = {
    'spec': (SPEC_STATUSES, SPEC_ALIASES),
    'run': (RUN_STATUSES, RUN_ALIASES),
    'task': (TASK_STATUSES, {}),
    'worker': (WORKER_STATUSES, {}),
    'evidence': (EVIDENCE_RESULTS, {}),
    'review': (REVIEW_RESULTS, {}),
}


def normalize(domain, value):
    """把旧值映射到分层枚举；未知值必须显式失败，不能静默放行。"""
    try:
        allowed, aliases = _DOMAINS[domain]
    except KeyError:
        raise GateError(f'Unknown status domain: {domain}') from None
    if not isinstance(value, str) or not value.strip():
        raise GateError(f'Empty status for {domain}')
    value = value.strip()
    value = aliases.get(value, value)
    if value not in allowed:
        raise GateError(f'Unknown {domain} status: {value}')
    return value


def task_for_run(run_status):
    value = normalize('run', run_status)
    return RUN_TO_TASK[value]


def run_for_review(review_status):
    review = normalize('review', review_status)
    return REVIEW_TO_RUN[review]


def is_terminal(run_status):
    return normalize('run', run_status) in {'accepted', 'failed', 'cancelled'}


def validate_operation_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', value):
        raise GateError('Invalid operation/scope identifier')
    return value
