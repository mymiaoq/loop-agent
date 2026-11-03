import tempfile
import unittest
from pathlib import Path

from docloop.governance import GateError
from docloop.operations import OperationLedger


class OperationLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = OperationLedger(Path(self.tmp.name), 'run-1')

    def test_begin_complete_is_idempotent(self):
        first = self.ledger.begin('worktree:prepare', 'worktree', {'branch': 'docloop/run-1'})
        self.assertEqual(first['status'], 'pending')
        self.assertEqual(self.ledger.begin('worktree:prepare', 'worktree')['status'], 'pending')
        done = self.ledger.complete('worktree:prepare', {'path': '/tmp/w'})
        self.assertEqual(done['status'], 'completed')
        self.assertEqual(self.ledger.begin('worktree:prepare', 'worktree')['status'], 'completed')
        self.assertEqual(len(self.ledger.history('worktree:prepare')), 2)

    def test_failed_operation_can_retry_with_attempt(self):
        self.ledger.begin('archive', 'archive')
        self.ledger.fail('archive', 'temporary')
        retry = self.ledger.begin('archive', 'archive')
        self.assertEqual(retry['status'], 'pending')
        self.assertEqual(retry['record']['attempt'], 2)
        self.ledger.complete('archive')
        self.assertEqual(self.ledger.begin('archive', 'archive')['status'], 'completed')

    def test_complete_or_fail_requires_pending_and_scope_is_safe(self):
        with self.assertRaises(GateError):
            self.ledger.complete('missing')
        with self.assertRaises(GateError):
            self.ledger.fail('missing', 'x')
        for scope in ('../escape', 'a/b', ''):
            with self.subTest(scope=scope), self.assertRaises(GateError):
                OperationLedger(Path(self.tmp.name), scope)
        with self.assertRaises(GateError):
            self.ledger.begin('../escape', 'x')
