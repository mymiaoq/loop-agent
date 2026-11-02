"""项目唯一 Skill 读取入口：每次从本地磁盘读取，按阶段生成 Agent 输入。"""
import json
import re
from pathlib import Path
import yaml
from .governance import GateError, sha256
from .superpowers import inspect_superpowers

STAGE_ROLES = {'spec': 'spec-agent', 'plan': 'orchestrator-agent',
               'implement': 'implement-agent', 'verify': 'verify-agent',
               'review': 'review-agent', 'archive': 'orchestrator-agent',
               'recovery': 'orchestrator-agent'}


class SkillRegistry:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        path = self.root / '.docloop/project.yaml'
        try:
            self.config = yaml.safe_load(path.read_text(encoding='utf-8'))
        except (OSError, yaml.YAMLError) as error:
            raise GateError('Cannot read project Skill configuration') from error
        if not isinstance(self.config, dict):
            raise GateError('Project Skill configuration must be an object')
        self.settings = self.config.get('skill_runtime', {})
        self.validate_routes()

    def validate_routes(self):
        if not isinstance(self.settings, dict):
            raise GateError('skill_runtime must be an object')
        bootstrap = self.settings.get('bootstrap', [])
        stages = self.settings.get('stages', {})
        if not isinstance(bootstrap, list) or not isinstance(stages, dict) or not stages:
            raise GateError('Skill bootstrap/stages configuration is invalid')
        refs = list(bootstrap)
        for stage, selected in stages.items():
            if stage not in STAGE_ROLES or not isinstance(selected, list) or not selected:
                raise GateError(f'Invalid Skill route for stage: {stage}')
            refs.extend(selected)
        for ref in refs:
            self._parse_ref(ref)

    @staticmethod
    def _parse_ref(ref):
        if not isinstance(ref, str):
            raise GateError('Skill references must be strings')
        namespace, separator, name = ref.partition(':')
        if not separator:
            namespace, name = 'docloop', ref
        if namespace not in {'docloop', 'superpowers'} or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name):
            raise GateError(f'Invalid project Skill reference: {ref}')
        return namespace, name

    def _location(self, ref: str):
        namespace, name = self._parse_ref(ref)
        if namespace == 'superpowers':
            config = self.config['superpowers']
            if not config.get('enabled') or not config.get('install_path'):
                raise GateError('Project-local Superpowers loading is disabled or unconfigured')
            if config.get('integrity_policy', 'strict') == 'strict':
                inspect_superpowers(self.root, config)
            elif config.get('integrity_policy') != 'editable':
                raise GateError('Unknown Superpowers integrity policy')
            resource_root = (self.root / config['install_path']).resolve()
            directory = resource_root / 'skills' / name
        else:
            resource_root = (self.root / self.settings.get('docloop_path', '.docloop/skills')).resolve()
            directory = resource_root / name
        if not resource_root.is_relative_to(self.root / '.docloop'):
            raise GateError('Skill root must be inside this project .docloop')
        path = (directory / 'SKILL.md').resolve()
        if not path.is_relative_to(resource_root):
            raise GateError('Skill path escapes project directory')
        return f'{namespace}:{name}', name, path, resource_root

    def _read(self, path: Path):
        path = path.resolve()
        if not path.is_relative_to(self.root / '.docloop'):
            raise GateError('Instruction file resolves outside project .docloop')
        try:
            raw = path.read_bytes()
            return {'path': path.relative_to(self.root).as_posix(), 'sha256': sha256(raw),
                    'content': raw.decode('utf-8-sig')}
        except (OSError, UnicodeError) as error:
            raise GateError(f'Cannot read project-local instruction file: {path}') from error

    def load(self, ref: str):
        qualified, name, path, _ = self._location(ref)
        document = self._read(path)
        parts = document['content'].split('---', 2)
        try:
            metadata = yaml.safe_load(parts[1]) if len(parts) == 3 else None
        except yaml.YAMLError as error:
            raise GateError(f'Invalid Skill frontmatter: {qualified}') from error
        if not isinstance(metadata, dict) or metadata.get('name') != name or not metadata.get('description'):
            raise GateError(f'Skill name/description missing or mismatched: {qualified}')
        return {**document, 'ref': qualified, 'name': name,
                'directory': path.parent.relative_to(self.root).as_posix()}

    def read_resource(self, ref: str, relative_path: str):
        _, _, skill_path, resource_root = self._location(ref)
        path = (skill_path.parent / relative_path).resolve()
        if not path.is_relative_to(resource_root):
            raise GateError('Skill resource escapes project-local source tree')
        return self._read(path)

    def build_agent_input(self, stage: str, context: dict, *, spec=''):
        if stage not in STAGE_ROLES:
            raise GateError(f'Unknown Skill stage: {stage}')
        stages = self.settings.get('stages', {})
        if stage not in stages or not isinstance(stages[stage], list):
            raise GateError(f'No project-local Skill routing configured for {stage}')
        refs = list(dict.fromkeys([*self.settings.get('bootstrap', []), *stages[stage]]))
        if not refs:
            raise GateError('Agent Skill route is empty')
        skills = [self.load(ref) for ref in refs]
        if set(context.get('rules', [])) & set(context.get('excluded_rules', [])):
            raise GateError('Excluded rule requested in Agent input')
        rules = []
        base = (self.root / '.docloop/rules').resolve()
        for name in context.get('rules', []):
            path = (base / f'{name}.md').resolve()
            if not path.is_relative_to(base):
                raise GateError('Rule path escapes project')
            rules.append({**self._read(path), 'name': name})
        role = STAGE_ROLES[stage]
        role_document = self._read(self.root / '.docloop/agents' / f'{role}.md')
        header = ('Use these project-local role, rules and Skills for this stage. '
                  'Resolve superpowers:name and docloop:name through the project SkillRegistry. '
                  'Resolve relative references using each listed local Skill directory. '
                  'Skills do not grant tools or override approval and role gates.\n')
        documents = [role_document, *rules, *skills]
        instruction = header + '\n\n'.join(f'File: {doc["path"]}\nSHA256: {doc["sha256"]}\n{doc["content"]}'
                                             for doc in documents)
        packet = {'stage': stage, 'role': role, 'source': 'project-local',
                  'skills': [{k: doc[k] for k in ('ref', 'path', 'sha256', 'directory')} for doc in skills],
                  'rules': [{k: doc[k] for k in ('name', 'path', 'sha256')} for doc in rules],
                  'role_file': {'path': role_document['path'], 'sha256': role_document['sha256']},
                  'messages': [{'role': 'system', 'content': instruction},
                               {'role': 'user', 'content': json.dumps({'task_context': context, 'spec': spec}, ensure_ascii=False)}],
                  'runtime_loaded': True, 'model_invoked': False}
        packet['input_sha256'] = sha256(json.dumps(packet, ensure_ascii=False, sort_keys=True).encode('utf-8'))
        return packet
