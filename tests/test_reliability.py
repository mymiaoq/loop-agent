import unittest
from docloop.reliability import Reliability, Limits, Blocked, classify_error


class ReliabilityTests(unittest.TestCase):
    def test_transient_errors_stop_after_three_retries(self):
        calls = []
        def broken():
            calls.append(1)
            raise TimeoutError('offline')
        with self.assertRaises(Blocked):
            Reliability(sleep=lambda _: None).call(broken)
        self.assertEqual(len(calls), 4)

    def test_business_errors_are_not_retried(self):
        calls = []
        def broken():
            calls.append(1)
            raise ValueError('business decision')
        with self.assertRaises(ValueError):
            Reliability().call(broken)
        self.assertEqual(len(calls), 1)

    def test_budgets_are_independent(self):
        r = Reliability(Limits(tokens=2, tools=1, llm=1))
        r.charge('tokens', 2)
        r.charge('tools', 1)
        r.charge('llm', 1)
        with self.assertRaises(Blocked):
            r.charge('tokens', 1)
        with self.assertRaises(ValueError):
            r.charge('tools', -1)

    def test_no_progress_and_repair_limit(self):
        r = Reliability()
        r.repair('error-a', 'diff-0')
        r.repair('error-a', 'diff-0')
        with self.assertRaises(Blocked):
            r.repair('error-a', 'diff-0')
        r = Reliability()
        for i in range(3):
            r.repair('error', str(i))
        with self.assertRaises(Blocked):
            r.repair('error', 'new')

    def test_error_taxonomy_and_non_repairable_permission(self):
        self.assertEqual(classify_error(PermissionError('denied')), 'permission')
        self.assertEqual(classify_error(TimeoutError('slow')), 'timeout')
        self.assertEqual(classify_error(AssertionError('failed')), 'test')
        calls = []
        def denied():
            calls.append(1)
            raise PermissionError('denied')
        with self.assertRaises(PermissionError):
            Reliability(sleep=lambda _: None).call(denied)
        self.assertEqual(len(calls), 1)
        with self.assertRaises(Blocked):
            Reliability().repair('fp', 'progress', error_class='permission')

    def test_circuit_blocks_next_operation(self):
        r = Reliability(Limits(circuit_failures=2), sleep=lambda _: None)
        with self.assertRaises(Blocked):
            r.call(lambda: (_ for _ in ()).throw(ConnectionError('network')), external=True)
        with self.assertRaises(Blocked):
            r.call(lambda: self.fail('open circuit executed operation'), external=True)

    def test_elapsed_limits(self):
        now = [0.0]
        r = Reliability(Limits(task_seconds=1), clock=lambda: now[0])
        now[0] = 2
        with self.assertRaises(Blocked):
            r.charge('tools', 1)


class RepairLoopTests(unittest.TestCase):
    def test_repair_loop_retries_until_success_and_rejects_permission(self):
        from docloop.reliability import RepairLoop
        attempts = []
        repairs = []
        def operation():
            attempts.append(1)
            if len(attempts) < 3:
                raise AssertionError('still failing')
            return 'ok'
        loop = RepairLoop(Reliability())
        self.assertEqual(loop.run(operation, 'diff-1', repairs.append), 'ok')
        self.assertEqual(len(attempts), 3)
        self.assertEqual(len(repairs), 2)
        denied = RepairLoop(Reliability())
        with self.assertRaises(PermissionError):
            denied.run(lambda: (_ for _ in ()).throw(PermissionError('no')), 'diff-1')
