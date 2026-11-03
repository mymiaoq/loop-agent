import concurrent.futures
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from docloop.codex_runtime import CodexRuntime, CodexRuntimeError, resolve_command


FAKE = '''import json, os, pathlib, sys, time
sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
args = sys.argv[1:]
prompt = sys.stdin.read()
if 'CHILD:' in prompt:
 import subprocess
 marker = json.loads(prompt)['messages'][0]['content'].split('CHILD:',1)[1]
 code = "import pathlib,time; time.sleep(1.2); pathlib.Path(" + repr(marker) + ").write_text('alive')"
 subprocess.Popen([sys.executable, '-c', code])
 if 'ORPHAN_CHILD:' in prompt: sys.exit(0)
 time.sleep(20)
if 'WAIT' in prompt: time.sleep(20)
if 'FAIL' in prompt:
 print('secret-provider-token', file=sys.stderr); sys.exit(7)
if 'FLOOD' in prompt:
 print('x' * 100000); sys.exit(0)
if 'INCOMPLETE' in prompt:
 print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'fake'}})); sys.exit(0)
assert args[:5] == ['exec','--ephemeral','--ignore-user-config','--model','gpt-6.1-sol'], args
assert args[5:8] == ['--sandbox','read-only','--json'], args
assert args[8:10] == ['--disable','shell_tool'], args
cwd = pathlib.Path(args[args.index('--cd')+1])
assert cwd == pathlib.Path.cwd()
assert not list(cwd.rglob('auth.json'))
assert args[-2:] == ['--skip-git-repo-check','-']
print(json.dumps({'type':'item.completed','item':{'type':'reasoning','text':'private'}}))
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps({'prompt':prompt,'cwd':str(cwd)})}}))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':8,'output_tokens':3}}))
'''


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        script = Path(self.tmp.name) / 'fake.py'
        script.write_text(FAKE, encoding='utf-8')
        self.adapter = CodexRuntime(command=[sys.executable, str(script)])

    def test_prompt_arguments_and_auth_not_copied(self):
        result = self.adapter.complete([{'role':'user','content':'中文 $() ; data'}])
        data = json.loads(result['content'])
        self.assertIn('中文 $() ; data', data['prompt'])
        self.assertEqual(result['model'], 'gpt-6.1-sol')
        self.assertTrue(result['model_invoked'])
        self.assertEqual(result['usage']['input_tokens'], 8)
        self.assertFalse(Path(data['cwd']).exists())

    def test_timeout_and_cancel(self):
        with self.assertRaisesRegex(CodexRuntimeError, 'timeout'):
            self.adapter.complete([{'role':'user','content':'WAIT'}], timeout=.15)
        cancel = threading.Event()
        timer = threading.Timer(.15, cancel.set)
        timer.start()
        self.addCleanup(timer.cancel)
        with self.assertRaisesRegex(CodexRuntimeError, 'cancelled'):
            self.adapter.complete([{'role':'user','content':'WAIT'}], cancel_event=cancel)

    def test_errors_do_not_fallback_or_leak_stderr(self):
        for prompt in ['FAIL', 'INCOMPLETE']:
            with self.subTest(prompt=prompt), self.assertRaises(CodexRuntimeError) as error:
                self.adapter.complete([{'role':'user','content':prompt}])
            self.assertNotIn('secret', str(error.exception))

    def test_output_limit(self):
        adapter = CodexRuntime(command=self.adapter.command, output_limit=4096)
        with self.assertRaisesRegex(CodexRuntimeError, 'output limit'):
            adapter.complete([{'role':'user','content':'FLOOD'}])

    def test_concurrent_calls_have_separate_directories(self):
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: self.adapter.complete([{'role':'user','content':'ok'}]), range(2)))
        self.assertNotEqual(*[json.loads(r['content'])['cwd'] for r in results])

    def test_timeout_terminates_owned_child_process(self):
        marker = Path(self.tmp.name) / 'child-survived.txt'
        with self.assertRaisesRegex(CodexRuntimeError, 'timeout'):
            self.adapter.complete([{'role':'user','content':'CHILD:' + str(marker)}], timeout=.4)
        time.sleep(1.3)
        self.assertFalse(marker.exists())

    def test_parent_exit_does_not_leave_child_with_inherited_pipes(self):
        marker = Path(self.tmp.name) / 'orphan-survived.txt'
        with self.assertRaisesRegex(CodexRuntimeError, 'timeout'):
            self.adapter.complete([{'role':'user','content':'ORPHAN_CHILD:' + str(marker)}], timeout=.4)
        time.sleep(1.3)
        self.assertFalse(marker.exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows job ownership')
    def test_job_assignment_failure_does_not_send_prompt_or_fallback(self):
        marker = Path(self.tmp.name) / 'unowned-child.txt'
        with patch('docloop.codex_runtime._WindowsJob', side_effect=OSError('secret ownership details')):
            with self.assertRaisesRegex(CodexRuntimeError, '^Windows process ownership unavailable$'):
                self.adapter.complete([{'role':'user','content':'CHILD:' + str(marker)}])
        time.sleep(1.3)
        self.assertFalse(marker.exists())

    def test_resolve_portable_package_native_before_node(self):
        root = Path(self.tmp.name)
        shim = root / 'codex.cmd'
        shim.touch()
        package = root / 'node_modules/@openai/codex'
        native = package / 'node_modules/@openai/codex-win32-x64/vendor/x/codex/codex.exe'
        native.parent.mkdir(parents=True)
        header = bytearray(132)
        header[:2] = b'MZ'
        header[60:64] = (128).to_bytes(4, 'little')
        header[128:] = b'PE\x00\x00'
        native.write_bytes(header)
        with patch('docloop.codex_runtime.shutil.which', side_effect=lambda name: str(shim) if name in {'codex', 'codex.cmd'} else None), patch.dict('os.environ', {'CODEX_APP_RUNTIME_CLI_PATH': ''}):
            self.assertEqual(resolve_command(), [str(native.resolve())])
        native.unlink()
        entry = package / 'bin/codex.js'
        entry.parent.mkdir(parents=True)
        entry.touch()
        with patch('docloop.codex_runtime.shutil.which', side_effect=lambda name: str(shim) if name == 'codex.cmd' else sys.executable if name == 'node.exe' else None), patch.dict('os.environ', {'CODEX_APP_RUNTIME_CLI_PATH': ''}):
            self.assertEqual(resolve_command(), [str(Path(sys.executable).resolve()), str(entry.resolve())])

    def test_env_runtime_must_be_native_executable(self):
        invalid = Path(self.tmp.name) / 'codex.exe'
        invalid.write_text('not native')
        with patch('docloop.codex_runtime.shutil.which', return_value=None), patch.dict('os.environ', {'CODEX_APP_RUNTIME_CLI_PATH': str(invalid)}):
            with self.assertRaises(CodexRuntimeError):
                resolve_command()


if __name__ == '__main__':
    unittest.main()

