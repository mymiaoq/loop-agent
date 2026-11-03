import unittest

from docloop.governance import GateError
from docloop.status import (RUN_STATUSES, TASK_STATUSES, is_terminal, normalize,
                            run_for_review, task_for_run, validate_operation_id)


class StatusContractTests(unittest.TestCase):
    def test_legacy_spec_and_run_values_are_normalized(self):
        self.assertEqual(normalize('spec', 'active'), 'approved')
        self.assertEqual(normalize('run', 'planned'), 'ready')
        self.assertEqual(normalize('run', 'accepted'), 'accepted')
        self.assertIn('awaiting_acceptance', RUN_STATUSES)
        self.assertIn('verified', TASK_STATUSES)

    def test_unknown_domain_or_value_is_rejected(self):
        for domain, value in [('spec', 'done'), ('run', 'completed'), ('task', 'x'), ('review', 'passed')]:
            with self.subTest(domain=domain, value=value), self.assertRaises(GateError):
                normalize(domain, value)
        with self.assertRaises(GateError):
            normalize('unknown', 'draft')

    def test_task_and_review_mapping_is_explicit(self):
        self.assertEqual(task_for_run('in_progress'), 'running')
        self.assertEqual(task_for_run('accepted'), 'verified')
        self.assertEqual(task_for_run('blocked'), 'blocked')
        self.assertEqual(run_for_review('approved'), 'awaiting_acceptance')
        self.assertEqual(run_for_review('rejected'), 'implemented')
        self.assertTrue(is_terminal('accepted'))
        self.assertFalse(is_terminal('awaiting_acceptance'))

    def test_operation_identifiers_are_restricted(self):
        self.assertEqual(validate_operation_id('worktree:prepare:run-1'), 'worktree:prepare:run-1')
        for value in ('', '../escape', 'a b', 'x' * 200, None):
            with self.subTest(value=value), self.assertRaises(GateError):
                validate_operation_id(value)
