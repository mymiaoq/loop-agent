"""证据门禁和带散列清单的可复核归档。"""
import re
import shutil
from pathlib import Path
import yaml
from .governance import GateError, sha256


def validate_evidence(acceptance_ids: list[str], report: dict):
    if not acceptance_ids or len(set(acceptance_ids)) != len(acceptance_ids):
        raise GateError('Acceptance IDs required and must be unique')
    if report.get('producer') != 'verify-agent' or not re.fullmatch(r'[a-f0-9]{40,64}', report.get('commit', '')):
        raise GateError('Independent verifier and Commit SHA required')
    covered, seen = set(), set()
    for check in report.get('checks', []):
        required = ('id', 'test_case_id', 'command_or_method', 'observed', 'evidence')
        if any(not check.get(key) for key in required) or check.get('result') != 'passed':
            raise GateError('Mandatory evidence missing, failed, blocked or not_run')
        if 'test_layer' in check and (not isinstance(check['test_layer'], str) or not check['test_layer'].strip()):
            raise GateError('Invalid evidence test layer')
        if 'exit_code' in check and not isinstance(check['exit_code'], int):
            raise GateError('Invalid evidence exit code')
        for key in ('log_path', 'screenshot_path', 'executed_at'):
            if key in check and not isinstance(check[key], str):
                raise GateError('Invalid evidence path or timestamp')
        if check['id'] in seen:
            raise GateError('Duplicate verification ID')
        seen.add(check['id'])
        covered.update(check.get('requirement_ids', []))
    if set(acceptance_ids) - covered:
        raise GateError('Acceptance evidence coverage incomplete')
    if report.get('failures') or report.get('blocked_by'):
        raise GateError('Unresolved failures or blockers')


def archive_change(root: Path, change_id: str, source: Path):
    target = root / '文档' / '变更记录' / change_id
    checklist = next((name for name in ('checklist.md', 'checkList.md')
                      if (source / name).is_file()), None)
    required = ('spec.md', 'decisions.md', 'tasks.md', 'evidence.yaml', 'review.yaml')
    if checklist is None or any(not (source / item).is_file() for item in required):
        raise GateError('Archive inputs incomplete')
    if target.exists():
        manifest = yaml.safe_load((target / 'manifest.yaml').read_text(encoding='utf-8'))
        if all(sha256((target / name).read_bytes()) == digest
               and sha256((source / name).read_bytes()) == digest
               for name, digest in manifest['files'].items()):
            return target
        raise GateError('Existing archive differs; refusing overwrite')
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(target.name + '.staging')
    if staging.exists():
        raise GateError('Incomplete archive staging exists; inspect before recovery')
    shutil.copytree(source, staging)
    hashes = {p.relative_to(staging).as_posix(): sha256(p.read_bytes())
              for p in sorted(staging.rglob('*')) if p.is_file()}
    (staging / 'manifest.yaml').write_text(yaml.safe_dump({
        'change_id': change_id, 'version': 1, 'files': hashes}, allow_unicode=True), encoding='utf-8')
    staging.rename(target)
    return target
