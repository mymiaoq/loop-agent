"""角色、状态与任务输入契约。"""
from dataclasses import dataclass, field
from .governance import GateError

TRANSITIONS = {
    ('draft', 'ready'): 'orchestrator-agent',
    ('ready', 'in_progress'): 'orchestrator-agent',
    ('in_progress', 'implemented'): 'implement-agent',
    ('implemented', 'verified'): 'verify-agent',
    ('verified', 'accepted'): 'orchestrator-agent',
}
ROLES = {'orchestrator-agent', 'spec-agent', 'implement-agent', 'verify-agent', 'review-agent'}


def transition(current: str, target: str, actor: str) -> str:
    if actor not in ROLES or current in {'accepted', 'cancelled', 'failed'}:
        raise GateError('Terminal state or unknown actor')
    if target in {'blocked', 'needs_input', 'failed', 'cancelled'}:
        return target
    if TRANSITIONS.get((current, target)) != actor:
        raise GateError(f'Forbidden transition: {current} -> {target} by {actor}')
    return target


@dataclass
class TaskContext:
    change_id: str
    domains: list[str] = field(default_factory=lambda: ['workflow'])
    rules: list[str] = field(default_factory=lambda: ['code-standard', 'verification-standard'])
    skills: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=lambda: ['static'])
    allowed_paths: list[str] = field(default_factory=list)
    allowed_commands: list[list[str]] = field(default_factory=list)
    excluded_rules: list[str] = field(default_factory=list)

    def validate(self):
        if set(self.rules) & set(self.excluded_rules):
            raise GateError('Excluded rule was selected')
        if not self.change_id or not self.domains or not self.verification:
            raise GateError('Incomplete task_context')
