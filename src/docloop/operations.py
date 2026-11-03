"""外部副作用台账：记录执行前后状态，供恢复前核验；协作式，不是分布式锁。"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from .governance import GateError
from .status import validate_operation_id


class OperationLedger:
    def __init__(self, root: Path, scope: str):
        self.root = Path(root).resolve()
        self.scope = validate_operation_id(scope)
        self.path = self.root / '.docloop/operations' / (self.scope + '.jsonl')
        self._lock = RLock()

    def _read(self):
        if not self.path.is_file():
            return []
        rows = []
        try:
            for line in self.path.read_text(encoding='utf-8').splitlines():
                if line.strip():
                    row = json.loads(line)
                    if isinstance(row, dict):
                        rows.append(row)
        except (OSError, ValueError):
            raise GateError('Operation ledger is unreadable') from None
        return rows

    def _append(self, row):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n'
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())

    def _latest(self, operation_id):
        for row in reversed(self._read()):
            if row.get('operation_id') == operation_id:
                return row
        return None

    def begin(self, operation_id: str, kind: str, payload=None):
        operation_id = validate_operation_id(operation_id)
        if not isinstance(kind, str) or not kind.strip():
            raise GateError('Operation kind is required')
        with self._lock:
            latest = self._latest(operation_id)
            if latest and latest.get('status') == 'completed':
                return {'status': 'completed', 'record': latest}
            if latest and latest.get('status') == 'pending':
                return {'status': 'pending', 'record': latest}
            attempt = int(latest.get('attempt', 0)) + 1 if latest else 1
            row = {'operation_id': operation_id, 'kind': kind, 'status': 'pending',
                   'attempt': attempt, 'payload': payload or {},
                   'at': datetime.now(timezone.utc).isoformat()}
            self._append(row)
            return {'status': 'pending', 'record': row}

    def complete(self, operation_id: str, result=None):
        operation_id = validate_operation_id(operation_id)
        with self._lock:
            latest = self._latest(operation_id)
            if not latest or latest.get('status') != 'pending':
                raise GateError('No pending operation to complete')
            row = {'operation_id': operation_id, 'kind': latest['kind'], 'status': 'completed',
                   'attempt': latest['attempt'], 'result': result or {},
                   'at': datetime.now(timezone.utc).isoformat()}
            self._append(row)
            return row

    def fail(self, operation_id: str, error: str):
        operation_id = validate_operation_id(operation_id)
        with self._lock:
            latest = self._latest(operation_id)
            if not latest or latest.get('status') != 'pending':
                raise GateError('No pending operation to fail')
            row = {'operation_id': operation_id, 'kind': latest['kind'], 'status': 'failed',
                   'attempt': latest['attempt'], 'error': str(error)[:500],
                   'at': datetime.now(timezone.utc).isoformat()}
            self._append(row)
            return row

    def history(self, operation_id: str):
        operation_id = validate_operation_id(operation_id)
        return [row for row in self._read() if row.get('operation_id') == operation_id]
