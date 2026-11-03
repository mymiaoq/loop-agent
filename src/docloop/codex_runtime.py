"""Isolated read-only Codex CLI adapter; no fabricated fallback.

README: CodexRuntime().complete(messages, cancel_event=None, timeout=120)
returns {content, model, usage, model_invoked}. Messages contain role/content
strings. Existing local Codex login is used in place; credentials are never read
or copied. A fresh temporary read-only workspace is used for every invocation.
The subprocess command override is intended for deterministic local fixtures.
Errors expose fixed categories only, never raw provider output. No write-mode
execution API is provided. CLI JSONL is consumed in memory with a byte limit;
only final agent_message content and turn.completed usage are returned.
"""

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import threading
import time


MODEL = 'gpt-6.1-sol'


class CodexRuntimeError(RuntimeError):
    """Sanitized failure; no successful fallback is generated."""


def resolve_command():
    """Find native executable first; never invoke a .cmd shell shim."""
    paths = [os.environ.get('CODEX_APP_RUNTIME_CLI_PATH')]
    paths.extend(shutil.which(name) for name in ('codex.exe', 'codex', 'codex.cmd'))
    packages = []
    for found in filter(None, paths):
        path = Path(found).resolve()
        if _native_executable(path):
            return [str(path)]
        packages.append(path.parent / 'node_modules/@openai/codex')
        if path.name == 'codex.js' and path.parent.name == 'bin':
            packages.append(path.parent.parent)
    for package in packages:
        for candidate in sorted((package / 'node_modules/@openai/codex-win32-x64/vendor').glob('**/codex.exe')):
            if _native_executable(candidate):
                return [str(candidate.resolve())]
    node = shutil.which('node.exe') or shutil.which('node')
    for package in packages:
        entry = package / 'bin/codex.js'
        if node and entry.is_file():
            return [str(Path(node).resolve()), str(entry.resolve())]
    raise CodexRuntimeError('Codex CLI unavailable')


def _native_executable(path):
    if path.suffix.lower() != '.exe' or not path.is_file():
        return False
    try:
        with path.open('rb') as source:
            header = source.read(64)
            if len(header) != 64 or header[:2] != b'MZ':
                return False
            source.seek(int.from_bytes(header[60:64], 'little'))
            return source.read(4) == b'PE\x00\x00'
    except OSError:
        return False


def _terminate_tree(process):
    # PID 只能来自本次创建且尚未回收的 Popen，不能由调用方提供。
    if os.name == 'nt' and process.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(
            [str(Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/taskkill.exe'),
             '/PID', str(process.pid), '/T', '/F'],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=10, check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=10)


class _WindowsJob:
    """Keep all inherited children owned even when their parent exits early."""

    def __init__(self, process):
        import ctypes
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64),
                        ('PerJobUserTimeLimit', ctypes.c_int64),
                        ('LimitFlags', wintypes.DWORD),
                        ('MinimumWorkingSetSize', ctypes.c_size_t),
                        ('MaximumWorkingSetSize', ctypes.c_size_t),
                        ('ActiveProcessLimit', wintypes.DWORD),
                        ('Affinity', ctypes.c_size_t),
                        ('PriorityClass', wintypes.DWORD),
                        ('SchedulingClass', wintypes.DWORD)]

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                         'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [('BasicLimitInformation', BasicLimits), ('IoInfo', IoCounters),
                        ('ProcessMemoryLimit', ctypes.c_size_t),
                        ('JobMemoryLimit', ctypes.c_size_t),
                        ('PeakProcessMemoryUsed', ctypes.c_size_t),
                        ('PeakJobMemoryUsed', ctypes.c_size_t)]

        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.api.SetInformationJobObject.restype = wintypes.BOOL
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.AssignProcessToJobObject.restype = wintypes.BOOL
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise CodexRuntimeError('Windows process ownership unavailable')
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
        configured = self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits))
        if not configured or not self.api.AssignProcessToJobObject(self.handle, wintypes.HANDLE(int(process._handle))):
            self.close()
            raise CodexRuntimeError('Windows process ownership unavailable')

    def close(self):
        if self.handle:
            handle, self.handle = self.handle, None
            if not self.api.CloseHandle(handle):
                raise CodexRuntimeError('Windows process ownership cleanup failed')


class CodexRuntime:
    """Thread-safe synchronous read-only completion adapter."""

    def __init__(self, command=None, output_limit=4 * 1024 * 1024):
        self.command = tuple(command or resolve_command())
        if not self.command or not Path(self.command[0]).is_absolute():
            raise ValueError('command executable must be absolute')
        if Path(self.command[0]).suffix.lower() in {'.cmd', '.bat'}:
            raise ValueError('shell shims are prohibited')
        if output_limit < 1:
            raise ValueError('output_limit must be positive')
        self.output_limit = output_limit

    def complete(self, messages, cancel_event=None, timeout=120):
        """Run one ephemeral model turn or raise a sanitized error."""
        if timeout <= 0:
            raise ValueError('timeout must be positive')
        if not isinstance(messages, (list, tuple)) or not messages:
            raise ValueError('messages must be nonempty')
        for message in messages:
            if not isinstance(message, dict) or not isinstance(message.get('role'), str) or not isinstance(message.get('content'), str):
                raise ValueError('messages require string role and content')
        prompt = json.dumps({'messages': messages}, ensure_ascii=False).encode('utf-8')
        if cancel_event is not None and cancel_event.is_set():
            raise CodexRuntimeError('cancelled')
        with tempfile.TemporaryDirectory(prefix='docloop-codex-') as workspace:
            args = [*self.command, 'exec', '--ephemeral', '--ignore-user-config',
                    '--model', MODEL, '--sandbox', 'read-only', '--json', '--disable', 'shell_tool', '--cd',
                    workspace, '--skip-git-repo-check', '-']
            return self._run(args, workspace, prompt, cancel_event, timeout)

    def _run(self, args, workspace, prompt, cancel_event, timeout):
        options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
        try:
            process = subprocess.Popen(args, cwd=workspace, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)
        except OSError:
            raise CodexRuntimeError('Codex CLI launch failed') from None
        job = None
        try:
            # 输入前绑定所有权；失败时不发送 prompt，不允许降级为无 Job 执行。
            if os.name == 'nt':
                job = _WindowsJob(process)
        except Exception:
            _terminate_tree(process)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()
            raise CodexRuntimeError('Windows process ownership unavailable') from None
        chunks, total, overflow = [], [0], threading.Event()
        lock = threading.Lock()

        def drain(stream, collect):
            try:
                while data := stream.read(4096):
                    with lock:
                        total[0] += len(data)
                        if total[0] > self.output_limit:
                            overflow.set()
                        elif collect:
                            chunks.append(data)
            finally:
                stream.close()

        def feed():
            try:
                process.stdin.write(prompt)
                process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
            finally:
                process.stdin.close()

        workers = [threading.Thread(target=drain, args=(process.stdout, True), daemon=True),
                   threading.Thread(target=drain, args=(process.stderr, False), daemon=True),
                   threading.Thread(target=feed, daemon=True)]
        for worker in workers:
            worker.start()
        deadline = time.monotonic() + timeout
        failure = None
        try:
            while True:
                if overflow.is_set():
                    failure = 'output limit exceeded'
                elif cancel_event is not None and cancel_event.is_set():
                    failure = 'cancelled'
                elif time.monotonic() >= deadline:
                    failure = 'timeout'
                if failure:
                    raise CodexRuntimeError(failure)
                if process.poll() is not None and all(not w.is_alive() for w in workers):
                    break
                time.sleep(.02)
            if process.returncode:
                raise CodexRuntimeError('Codex provider execution failed')
            return self._parse(b''.join(chunks))
        finally:
            try:
                if job is not None:
                    job.close()
            finally:
                _terminate_tree(process)
                for worker in workers:
                    worker.join(timeout=2)

    @staticmethod
    def _parse(raw):
        content, usage, completed = [], None, False
        try:
            for line in raw.decode('utf-8').splitlines():
                if not line.strip():
                    continue
                event = json.loads(line)
                if event.get('type') in {'error', 'turn.failed'}:
                    raise CodexRuntimeError('Codex provider execution failed')
                item = event.get('item', {})
                if event.get('type') == 'item.completed' and item.get('type') == 'agent_message':
                    text = item.get('text')
                    if isinstance(text, str):
                        content.append(text)
                if event.get('type') == 'turn.completed':
                    completed, usage = True, event.get('usage')
        except (ValueError, UnicodeError, AttributeError):
            raise CodexRuntimeError('invalid Codex JSONL') from None
        if not completed or not content or not isinstance(usage, dict):
            raise CodexRuntimeError('incomplete Codex response')
        return {'content': '\n'.join(content), 'model': MODEL,
                'usage': usage, 'model_invoked': True}
