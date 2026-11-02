import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WorkbenchStartupTests(unittest.TestCase):
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
