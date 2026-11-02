"""需求控制中心：来源、审批与不可覆盖基线。"""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


class GateError(ValueError):
    """违反审批、权限或交付门禁。"""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: dict, exclusive=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x' if exclusive else 'w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


class Governance:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def path(self, change_id: str) -> Path:
        if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', change_id)
                or change_id.upper() in {'CON', 'PRN', 'AUX', 'NUL',
                                         *[f'COM{i}' for i in range(10)],
                                         *[f'LPT{i}' for i in range(10)]}):
            raise GateError('Invalid change ID')
        path = self.root / '.docloop' / 'changes' / change_id
        if not path.resolve().is_relative_to(self.root):
            raise GateError('Change path escapes project root')
        return path

    def create(self, change_id: str, spec: str, source='user-input'):
        if not spec.strip():
            raise GateError('Spec cannot be empty')
        path = self.path(change_id)
        path.mkdir(parents=True, exist_ok=False)
        (path / 'spec.md').write_bytes(spec.encode('utf-8'))
        (path / 'decisions.md').write_text('# Decisions\nNo approved decisions yet.\n', encoding='utf-8')
        write_json(path / 'sources.json', {'source': source, 'sha256': sha256(spec.encode()),
                   'lines': [{'line': i, 'text': line} for i, line in enumerate(spec.splitlines(), 1)]})

    def digest(self, change_id: str) -> str:
        return sha256((self.path(change_id) / 'spec.md').read_bytes())

    def approve(self, change_id: str, expected_hash: str, approver: str):
        if not approver.strip() or self.digest(change_id) != expected_hash:
            raise GateError('Explicit approver and current Spec SHA256 required')
        path = self.path(change_id)
        if (path / 'baseline').exists():
            raise GateError('Baseline exists; create a new change/version')
        (path / 'baseline').mkdir()
        raw = (path / 'spec.md').read_bytes()
        # 原样保存已审批字节，不重排或格式化用户的 Spec。
        (path / 'baseline/spec.md').write_bytes(raw)
        write_json(path / 'baseline/approval.json', {
            'sha256': expected_hash, 'approver': approver,
            'approved_at': datetime.now(timezone.utc).isoformat(), 'version': 1}, exclusive=True)
        return expected_hash

    def assert_baseline(self, change_id: str) -> str:
        path = self.path(change_id)
        try:
            record = json.loads((path / 'baseline/approval.json').read_text(encoding='utf-8'))
            baseline_hash = sha256((path / 'baseline/spec.md').read_bytes())
        except (OSError, ValueError, KeyError) as error:
            raise GateError('Approved baseline missing or invalid') from error
        if not (record.get('approver') and record.get('sha256') == baseline_hash == self.digest(change_id)):
            raise GateError('Spec differs from approved baseline; change request required')
        return baseline_hash
