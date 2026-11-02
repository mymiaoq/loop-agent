import sys
import tempfile
import unittest
from pathlib import Path
from docloop.adapters import ToolAdapter
from docloop.governance import GateError
from docloop.reliability import Blocked
from docloop.execution_lock import run_lock


class ToolTests(unittest.TestCase):
    def test_allowlist_is_exact_and_scope_is_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            argv = [sys.executable, '-c', 'print(42)']
            tool = ToolAdapter([root], [argv])
            self.assertEqual(tool.run(argv, root).stdout.strip(), '42')
            with self.assertRaises(GateError):
                tool.run(argv + ['extra'], root)
            with self.assertRaises(GateError):
                tool.run(argv, root.parent)

    def test_timeout_stops_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            argv = [sys.executable, '-c', 'import time; time.sleep(10)']
            with self.assertRaises(Blocked):
                ToolAdapter([tmp], [argv], timeout=0.1).run(argv, Path(tmp))

    def test_second_writer_cannot_enter_same_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            with run_lock(Path(tmp), 'run-1'):
                with self.assertRaises(GateError):
                    with run_lock(Path(tmp), 'run-1'):
                        self.fail('second concurrent writer entered')
            with run_lock(Path(tmp), 'run-1'):
                pass
