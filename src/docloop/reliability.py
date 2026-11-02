"""独立计量的预算、有限重试、修复进展和外部熔断。"""
import hashlib
import time
from dataclasses import asdict, dataclass


class Blocked(RuntimeError):
    pass


@dataclass(frozen=True)
class Limits:
    retries: int = 3
    repairs: int = 3
    no_progress: int = 2
    llm: int = 30
    tokens: int = 100000
    tools: int = 100
    model_rounds: int = 20
    task_seconds: float = 600
    run_seconds: float = 3600
    concurrency: int = 1
    graph_steps: int = 50
    circuit_failures: int = 5


def fingerprint(error: Exception) -> str:
    return hashlib.sha256(f'{type(error).__name__}:{error}'.encode()).hexdigest()


class Reliability:
    def __init__(self, limits=None, *, clock=time.monotonic, sleep=time.sleep):
        self.limits = limits or Limits()
        if any(value <= 0 for value in asdict(self.limits).values()):
            raise ValueError('Limits must be positive')
        self.clock, self.sleep = clock, sleep
        self.started = self.task_started = clock()
        self.usage = {'llm': 0, 'tokens': 0, 'tools': 0, 'model_rounds': 0, 'concurrency': 0, 'graph_steps': 0}
        self.repairs = self.stalled = self.failures = 0
        self.last_progress = None
        self.fingerprints = []

    def check_time(self):
        if self.clock() - self.started > self.limits.run_seconds:
            raise Blocked('Run time budget exhausted')
        if self.clock() - self.task_started > self.limits.task_seconds:
            raise Blocked('Task time budget exhausted')

    def charge(self, kind: str, amount: int = 1):
        if kind not in self.usage or not isinstance(amount, int) or amount < 0:
            raise ValueError('Invalid budget charge')
        self.check_time()
        if self.usage[kind] + amount > getattr(self.limits, kind):
            raise Blocked(f'{kind} budget exhausted')
        self.usage[kind] += amount

    def call(self, operation, *, external=False):
        for attempt in range(self.limits.retries + 1):
            self.check_time()
            if external and self.failures >= self.limits.circuit_failures:
                raise Blocked('External circuit open; explicit recovery required')
            try:
                result = operation()
                self.check_time()
                self.failures = 0
                return result
            except (TimeoutError, ConnectionError) as error:
                self.failures += 1
                self.fingerprints.append(fingerprint(error))
                if attempt == self.limits.retries:
                    raise Blocked('Transient retry budget exhausted') from error
                self.sleep(min(2 ** attempt, 4))
        raise AssertionError('unreachable')

    def repair(self, error_fingerprint: str, progress: str):
        self.check_time()
        if self.repairs >= self.limits.repairs:
            raise Blocked('Repair round budget exhausted')
        self.stalled = self.stalled + 1 if progress == self.last_progress else 0
        if self.stalled >= self.limits.no_progress:
            raise Blocked('No progress for two rounds')
        self.last_progress = progress
        self.fingerprints.append(error_fingerprint)
        self.repairs += 1
