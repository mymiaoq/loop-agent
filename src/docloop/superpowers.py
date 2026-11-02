"""校验随项目收录的上游文件；存在与实际运行加载分别报告。"""
import json
import re
from pathlib import Path
from .governance import GateError, sha256


def inspect_superpowers(root: Path, config: dict):
    root = Path(root).resolve()
    report = {'commit': config['commit'], 'enabled': config['enabled'],
              'installed': False, 'integrity_verified': False, 'runtime_loaded': False}
    if not config.get('install_path'):
        return report
    install = (root / config['install_path']).resolve()
    manifest_path = (root / config.get('manifest_path', '.docloop/superpowers.lock.json')).resolve()
    if not install.is_relative_to(root / '.docloop') or not manifest_path.is_relative_to(root / '.docloop'):
        raise GateError('Superpowers source or manifest outside .docloop')
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest['commit'] != config['commit'] or manifest['repository'] != config['repository']:
            raise GateError('Superpowers source differs from configured pin')
        files = manifest['files']
        if not isinstance(files, dict) or not files or 'LICENSE' not in files:
            raise GateError('Superpowers manifest incomplete')
        policy = config.get('integrity_policy', 'strict')
        if policy not in {'strict', 'editable'}:
            raise GateError('Unknown Superpowers integrity policy')
        modified, missing = [], []
        for name, record in files.items():
            path = (install / name).resolve()
            if not path.is_relative_to(install):
                raise GateError(f'Superpowers path escapes source directory: {name}')
            expected = record.get('sha256', '')
            if not re.fullmatch(r'[a-f0-9]{64}', expected):
                raise GateError(f'Invalid upstream Hash: {name}')
            if not path.is_file():
                missing.append(name)
            elif sha256(path.read_bytes()) != expected:
                modified.append(name)
        actual = {path.relative_to(install).as_posix() for path in install.rglob('*') if path.is_file()}
        for name in actual:
            if not (install / name).resolve().is_relative_to(install):
                raise GateError('Superpowers file resolves outside source directory')
        added = sorted(actual - set(files))
        matches = not (modified or missing or added)
        if policy == 'strict' and not matches:
            raise GateError('Superpowers tree differs from manifest')
        if 'LICENSE' not in actual:
            raise GateError('Superpowers LICENSE missing')
    except (OSError, ValueError, KeyError, TypeError) as error:
        if isinstance(error, GateError):
            raise
        raise GateError('Superpowers source or manifest invalid') from error
    skills = sorted(name.split('/')[1] for name in actual
                    if name.startswith('skills/') and name.endswith('/SKILL.md') and name.count('/') == 2)
    if 'using-superpowers' not in skills or 'brainstorming' not in skills:
        raise GateError('Superpowers bootstrap or brainstorming missing')
    return {**report, 'installed': True, 'integrity_verified': matches, 'upstream_matches': matches,
            'integrity_policy': policy, 'changes': {'modified': sorted(modified),
            'missing': sorted(missing), 'added': added},
            'install_path': config['install_path'], 'file_count': len(actual),
            'skills': skills, 'skill_count': len(skills)}
