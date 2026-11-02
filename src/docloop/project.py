"""按领域加载 Profile、规则和 Skill 契约，检查上游锁定状态。"""
import re
from pathlib import Path
import yaml
from .governance import GateError

SKILL_FIELDS = ('name', 'description')
REQUIRED_SKILLS = {'document-parser', 'spec-create', 'plan-create', 'checklist-create',
                   'project-bootstrap', 'test-runner', 'audit-recorder', 'recovery-diagnosis',
                   'project-archiving', 'component-generator', 'api-contract',
                   'backend-code-generator', 'frontend-design', 'frontend-quality-check', 'security-check'}
SKILL_SECTIONS = ('用途', '触发条件', '输入 Schema', '允许工具', '执行步骤',
                  '输出 Schema', '失败处理', '完成条件', '禁止行为')


def read_yaml(path: Path):
    with path.open(encoding='utf-8') as stream:
        value = yaml.safe_load(stream)
    if not isinstance(value, dict):
        raise GateError(f'Expected YAML object: {path}')
    return value


def select_context(root: Path, domains=None):
    config = read_yaml(root / '.docloop/project.yaml')
    profile_path = (root / '.docloop/profiles' / f'{config["profile"]}.yaml').resolve()
    if not profile_path.is_relative_to((root / '.docloop/profiles').resolve()):
        raise GateError('Profile outside permitted directory')
    profile = read_yaml(profile_path)
    domains = domains or ['workflow']
    active = list(profile.get('base_rules', []))
    for domain in domains:
        active.extend(profile.get('domain_rules', {}).get(domain, []))
    active = list(dict.fromkeys(active))
    for rule in active:
        path = (root / '.docloop/rules' / f'{rule}.md').resolve()
        if not path.is_relative_to((root / '.docloop/rules').resolve()) or not path.is_file():
            raise GateError(f'Missing or invalid rule: {rule}')
    return config, profile, active


def inspect_project(root: Path):
    root = Path(root).resolve()
    config, profile, active = select_context(root)
    if not (root / 'AGENTS.md').is_file():
        raise GateError('Project AGENTS.md missing')
    agents = sorted(path.stem for path in (root / '.docloop/agents').glob('*.md'))
    expected = ['implement-agent', 'orchestrator-agent', 'review-agent', 'spec-agent', 'verify-agent']
    if agents != expected:
        raise GateError('Five specialized role definitions required')
    skills = []
    for path in sorted((root / '.docloop/skills').glob('*/SKILL.md')):
        content = path.read_text(encoding='utf-8')
        parts = content.split('---', 2)
        if len(parts) != 3:
            raise GateError(f'Skill frontmatter missing: {path}')
        metadata = yaml.safe_load(parts[1])
        if not isinstance(metadata, dict) or any(not metadata.get(key) for key in SKILL_FIELDS):
            raise GateError(f'Skill metadata missing: {path}')
        if metadata['name'] != path.parent.name:
            raise GateError(f'Skill name differs from directory: {path}')
        if any(f'## {section}' not in parts[2] for section in SKILL_SECTIONS):
            raise GateError(f'Skill contract incomplete: {path}')
        skills.append(metadata['name'])
    if REQUIRED_SKILLS - set(skills):
        raise GateError(f'Missing required Skills: {sorted(REQUIRED_SKILLS - set(skills))}')
    lock = config['superpowers']
    if not re.fullmatch(r'[a-f0-9]{40}', lock['commit']):
        raise GateError('Superpowers must pin a real Commit SHA')
    return {'status': 'passed', 'profile': config['profile'], 'agents': agents,
            'skills': skills, 'active_rules': active, 'superpowers': {
                'commit': lock['commit'], 'enabled': lock['enabled'],
                'runtime_loaded': False}, 'mode': 'framework',
            'limitations': ['Configuration validation does not prove model compliance or live business execution.']}
