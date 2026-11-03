import json
import os
import subprocess
import sys
import tempfile
import unittest
import time
import re
from pathlib import Path
import httpx
from unittest.mock import patch, MagicMock
from contextlib import nullcontext
from docloop.governance import GateError

ROOT = Path(__file__).resolve().parents[1]


class WorkbenchStartupTests(unittest.TestCase):
    def test_shutdown_waits_for_data_lock_after_port_closes(self):
        from docloop.workbench import stop_existing
        client = MagicMock()
        client.get.return_value.json.return_value = {'csrf_token': 'test'}
        client.post.return_value.json.return_value = {'ok': True}
        probe = MagicMock()
        probe.connect_ex.return_value = 1
        with patch('docloop.workbench.find_instance', return_value='http://127.0.0.1:1234'), \
             patch('httpx.Client') as factory, patch('docloop.workbench.socket.socket') as sockets, \
             patch('docloop.workbench.run_lock', side_effect=[GateError('busy'), nullcontext()]) as lock, \
             patch('docloop.workbench.time.sleep') as sleep:
            factory.return_value.__enter__.return_value = client
            sockets.return_value.__enter__.return_value = probe
            self.assertTrue(stop_existing(ROOT, ROOT, 1234)['ok'])
            self.assertEqual(lock.call_count, 2, 'Returned while old service still held data lock')
            sleep.assert_called_once()

    def test_restart_replaces_only_matching_instance_and_preserves_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            processes = []
            logs = []
            url = None
            def launch(name, data, port, *args):
                log = (base / (name + '.log')).open('w', encoding='utf-8')
                logs.append(log)
                process = subprocess.Popen([sys.executable, '-m', 'docloop.workbench',
                    '--root', str(ROOT), '--data-root', str(data), '--port', str(port), *args],
                    stdout=log, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                processes.append(process)
                return process, base / (name + '.log')
            def ready(process, log):
                for _ in range(150):
                    text = log.read_text(encoding='utf-8')
                    match = re.search(r'http://127\.0\.0\.1:\d+', text)
                    if match:
                        try:
                            if httpx.get(match[0] + '/api/health', trust_env=False).status_code == 200:
                                return match[0]
                        except httpx.HTTPError:
                            pass
                    if process.poll() is not None:
                        self.fail(text)
                    time.sleep(.1)
                self.fail('Startup timed out')
            try:
                old, log = launch('old', base / 'data', 0)
                url = ready(old, log)
                port = url.rsplit(':', 1)[1]
                state = httpx.get(url + '/api/state', trust_env=False).json()
                foreign, foreign_log = launch('foreign', base / 'other', port, '--restart')
                foreign.wait(timeout=20)
                self.assertNotEqual(foreign.returncode, 0)
                self.assertIsNone(old.poll(), foreign_log.read_text(encoding='utf-8'))
                new, log = launch('new', base / 'data', port, '--restart')
                ready(new, log)
                old.wait(timeout=15)
                self.assertEqual(old.returncode, 0)
                restored = httpx.get(url + '/api/state', trust_env=False).json()
                self.assertEqual(restored['projects'], state['projects'])
                self.assertNotEqual(restored['csrf_token'], state['csrf_token'])
            finally:
                # Windows venv启动器可能有子进程，先请求服务正常退出并释放数据锁。
                if url:
                    from docloop.workbench import stop_existing
                    stop_existing(ROOT, base / 'data', int(url.rsplit(':', 1)[1]))
                for process in processes:
                    if process.poll() is None:
                        process.wait(timeout=15)
                    process.wait(timeout=15)
                for log in logs:
                    log.close()

    def test_cli_preflight_and_native_batch_use_isolated_data_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, '-m', 'docloop', '--root', str(ROOT),
                'workbench', '--check', '--data-root', tmp], capture_output=True, text=True,
                encoding='utf-8', timeout=45)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['storage_backend'], 'sandbox-sqlite')
            if os.name == 'nt':
                result = subprocess.run([os.environ['COMSPEC'], '/d', '/c',
                    str(ROOT / '启动工作台.cmd'), '--check', '--data-root', tmp],
                    capture_output=True, text=True, encoding='utf-8', timeout=45)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('sandbox-sqlite', result.stdout)
