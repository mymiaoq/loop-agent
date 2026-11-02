import tempfile
import unittest
from pathlib import Path

from docloop.governance import Governance, GateError
from docloop.contracts import transition


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.gov = Governance(self.root)
        self.gov.create('change-1', '# Spec\nAC-001: runnable\n')

    def test_approval_required_and_hash_must_match(self):
        with self.assertRaises(GateError):
            self.gov.assert_baseline('change-1')
        with self.assertRaises(GateError):
            self.gov.approve('change-1', 'wrong', 'user')
        digest = self.gov.digest('change-1')
        self.gov.approve('change-1', digest, 'user')
        self.assertEqual(self.gov.assert_baseline('change-1'), digest)

    def test_baseline_cannot_be_overwritten_or_silently_updated(self):
        self.gov.approve('change-1', self.gov.digest('change-1'), 'user')
        with self.assertRaises(GateError):
            self.gov.approve('change-1', self.gov.digest('change-1'), 'user')
        self.gov.path('change-1').joinpath('spec.md').write_text('tampered', encoding='utf-8')
        with self.assertRaises(GateError):
            self.gov.assert_baseline('change-1')

    def test_paths_and_empty_approver_rejected(self):
        for name in ('../escape', 'a/b', '', 'CON', 'x..y'):
            with self.subTest(name=name), self.assertRaises(GateError):
                self.gov.create(name, 'spec')
        with self.assertRaises(GateError):
            self.gov.approve('change-1', self.gov.digest('change-1'), '')

    def test_role_cannot_skip_verification(self):
        with self.assertRaises(GateError):
            transition('implemented', 'verified', 'implement-agent')
        with self.assertRaises(GateError):
            transition('draft', 'accepted', 'orchestrator-agent')
        self.assertEqual(transition('implemented', 'verified', 'verify-agent'), 'verified')
