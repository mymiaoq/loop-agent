"""受控工具及显式演示角色适配器。真实模型适配器必须另行配置。"""
import json
import subprocess
import sys
from pathlib import Path
from .governance import GateError
from .reliability import Blocked, Reliability


class ToolAdapter:
    def __init__(self, allowed_paths, allowed_commands, reliability=None, timeout=30):
        self.paths = [Path(p).resolve() for p in allowed_paths]
        self.commands = [tuple(command) for command in allowed_commands]
        self.reliability = reliability or Reliability()
        self.timeout = timeout

    def run(self, argv: list[str], cwd: Path):
        workdir = Path(cwd).resolve()
        if not any(workdir.is_relative_to(root) for root in self.paths):
            raise GateError('Tool working directory outside allowed scope')
        # 白名单匹配完整 argv，禁止 shell、字符串拼接及任意附加参数。
        if not argv or tuple(argv) not in self.commands:
            raise GateError('Command not in exact argv allowlist')
        self.reliability.charge('tools')
        try:
            result = subprocess.run(argv, cwd=workdir, capture_output=True, text=True,
                                    encoding='utf-8', errors='replace', timeout=self.timeout, shell=False)
        except subprocess.TimeoutExpired as error:
            raise Blocked('Tool timeout; inspect side effects before retry') from error
        self.reliability.check_time()
        return result


class DemoAdapter:
    """仅证明编排控制流；不是通用编码 Agent。"""
    def __init__(self, sandbox: Path, reliability: Reliability):
        self.sandbox = sandbox
        self.reliability = reliability

    def implement(self, scenario: str):
        self.sandbox.mkdir(parents=True, exist_ok=True)
        commands = [
            ['git', 'init', '-b', 'demo'], ['git', 'add', 'result.json'],
            ['git', '-c', 'user.name=DocLoop Demo', '-c', 'user.email=demo@localhost',
             'commit', '-m', 'demo: create controlled artifact'],
            ['git', 'rev-parse', 'HEAD'],
        ]
        tools = ToolAdapter([self.sandbox], commands, self.reliability)
        if not (self.sandbox / '.git').exists():
            self._check(tools.run(commands[0], self.sandbox))
        (self.sandbox / 'result.json').write_text(json.dumps({
            'mode': 'demo', 'value': 0 if scenario == 'verification-failure' else 42}), encoding='utf-8')
        self._check(tools.run(commands[1], self.sandbox))
        result = tools.run(commands[2], self.sandbox)
        if result.returncode and 'nothing to commit' not in result.stdout:
            self._check(result)
        return self._check(tools.run(commands[3], self.sandbox)).stdout.strip()

    @staticmethod
    def _check(result):
        if result.returncode:
            raise Blocked(f'Tool failed ({result.returncode}): {result.stderr or result.stdout}')
        return result

    def verify(self, acceptance_ids, commit, logs: Path):
        # 验证者重新执行子进程检查，不消费实现者的“通过”描述。
        program = ('import json,pathlib; p=pathlib.Path("result.json"); '
                   'd=json.loads(p.read_text()); assert d["value"] == 42; '
                   'print("observed value=42; JSON parsed independently")')
        argv = [sys.executable, '-c', program]
        actual_commit = self.assert_commit(commit)
        tools = ToolAdapter([self.sandbox], [argv], self.reliability)
        result = tools.run(argv, self.sandbox)
        logs.mkdir(parents=True, exist_ok=True)
        log = logs / 'verification.txt'
        log.write_text(result.stdout + result.stderr, encoding='utf-8')
        return {
            'producer': 'verify-agent', 'mode': 'demo', 'commit': actual_commit,
            'status': 'passed' if result.returncode == 0 else 'failed',
            'checks': [{'id': f'V-{i:03}', 'test_case_id': f'TC-{i:03}',
                        'requirement_ids': [ac], 'type': 'static',
                        'command_or_method': subprocess.list2cmdline(argv),
                        'result': 'passed' if result.returncode == 0 else 'failed',
                        'observed': result.stdout.strip() or result.stderr.strip(),
                        'evidence': 'logs/verification.txt'} for i, ac in enumerate(acceptance_ids, 1)],
            'remaining_risks': ['Controlled demo only; no real business acceptance or model inference.'],
        }

    def assert_commit(self, commit):
        commands = [['git', 'rev-parse', 'HEAD'], ['git', 'status', '--porcelain', '--untracked-files=all']]
        tools = ToolAdapter([self.sandbox], commands, self.reliability)
        actual = self._check(tools.run(commands[0], self.sandbox)).stdout.strip()
        if actual != commit:
            raise GateError('Implementation Commit changed before verification')
        if self._check(tools.run(commands[1], self.sandbox)).stdout.strip():
            raise GateError('Implementation worktree/index differs from target Commit')
        return actual
