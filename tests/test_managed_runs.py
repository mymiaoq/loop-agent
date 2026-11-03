import json
import tempfile
import unittest
from pathlib import Path
from threading import Event
from docloop.workbench_store import WorkbenchStore, Conflict, NotFound
from docloop.managed_runs import ManagedRuns, validate_plan

PLAN = {'tasks': [{'id': 'TASK-001', 'description': '实现批准功能', 'acceptance_ids': ['AC-001']}],
        'test_cases': [{'id': 'TC-001', 'description': '验证批准功能', 'expected': '符合批准结果',
                        'task_ids': ['TASK-001'], 'acceptance_ids': ['AC-001']}]}


class Prep:
    def __init__(self):
        self.calls = []

    def prepare(self, pid, sid):
        self.calls.append((pid, sid))
        return {'docker_ready': True, 'status': 'prepared'}


class ManagedRunTests(unittest.TestCase):
    def test_plan_cannot_link_case_to_a_task_for_another_acceptance(self):
        value = {'tasks': [
            {'id': 'TASK-001', 'description': 'first', 'acceptance_ids': ['AC-001']},
            {'id': 'TASK-002', 'description': 'second', 'acceptance_ids': ['AC-002']}],
            'test_cases': [
                {'id': 'TC-001', 'description': 'wrong link', 'expected': 'value',
                 'task_ids': ['TASK-002'], 'acceptance_ids': ['AC-001']},
                {'id': 'TC-002', 'description': 'wrong link', 'expected': 'value',
                 'task_ids': ['TASK-001'], 'acceptance_ids': ['AC-002']}]}
        with self.assertRaises(ValueError):
            validate_plan(value, 'AC-001 first\nAC-002 second')
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = WorkbenchStore.sandbox(Path(self.temp.name))
        self.pid = self.store.create_project('fixture')['id']
        self.sid = self.store.create_spec(self.pid, 'fixture', 'AC-001 批准功能', 'sandbox', [], [])['id']
        self.prep, self.services = Prep(), []

    def tearDown(self):
        for service in self.services:
            service.close()
        self.store.close()
        self.temp.cleanup()

    def service(self, planner=lambda spec, stop, rid: PLAN):
        service = ManagedRuns(self.store, self.prep, planner)
        self.services.append(service)
        return service

    def approve(self):
        spec = self.store.spec(self.pid, self.sid)
        self.store.approve_spec(self.pid, self.sid, spec['sha256'], spec['revision'], 'fixture')

    def join(self, service, rid):
        result = service.wait(self.pid, rid, timeout=5)
        self.assertNotEqual('in_progress', result['status'])
        return result

    def test_approval_before_any_worker_or_run(self):
        service = self.service()
        with self.assertRaises(Conflict):
            service.start(self.pid, self.sid)
        self.assertEqual([], self.store.history(self.pid))
        self.assertEqual([], self.prep.calls)

    def test_async_cancel_wait_and_duplicate_start_and_project_isolation(self):
        entered, release = Event(), Event()
        def planner(spec, stop, rid):
            entered.set()
            stop.wait(5)
            release.set()
            return PLAN
        self.approve()
        service = self.service(planner)
        run = service.start(self.pid, self.sid)
        self.assertTrue(entered.wait(3))
        self.assertEqual('in_progress', run['status'])
        self.assertEqual(run['id'], service.start(self.pid, self.sid)['id'])
        other = self.store.create_project('other')['id']
        with self.assertRaises(NotFound):
            service.cancel(other, run['id'])
        self.assertFalse(release.is_set())
        service.cancel(self.pid, run['id'])
        result = self.join(service, run['id'])
        self.assertEqual('cancelled', result['status'])
        self.assertEqual([], self.prep.calls)
        self.assertFalse((self.store.root / 'runs' / run['id'] / 'plan.json').exists())

    def test_docker_ready_never_accepts_and_persists_plan_checkpoint(self):
        self.approve()
        service = self.service()
        run = service.start(self.pid, self.sid)
        result = self.join(service, run['id'])
        self.assertEqual('runtime', result['mode'])
        self.assertEqual('blocked', result['status'])
        self.assertFalse(result['result']['real_business_acceptance'])
        folder = self.store.root / 'runs' / run['id']
        self.assertEqual(PLAN, json.loads((folder / 'plan.json').read_text(encoding='utf-8')))
        self.assertTrue((folder / 'checkpoint.sqlite').exists())

    def test_invalid_plan_cannot_prepare(self):
        self.approve()
        service = self.service(lambda spec, stop, rid: {'tasks': [], 'test_cases': []})
        run = service.start(self.pid, self.sid)
        self.assertEqual('blocked', self.join(service, run['id'])['status'])
        self.assertEqual([], self.prep.calls)

    def test_restart_blocks_without_replaying_planner(self):
        self.approve()
        run = self.store.start_run(self.pid, self.sid, mode='runtime')
        service = self.service(lambda spec, stop, rid: self.fail('must not replay'))
        self.assertEqual('blocked', service.status(self.pid, run['id'])['status'])
        self.assertEqual([], self.prep.calls)

    def test_service_exclusion_and_project_run_exclusion(self):
        self.approve()
        service = self.service(lambda spec, stop, rid: (stop.wait(5), PLAN)[1])
        from docloop.governance import GateError
        with self.assertRaises(GateError):
            ManagedRuns(self.store, self.prep, lambda spec, stop, rid: PLAN)
        run = service.start(self.pid, self.sid)
        other = self.store.create_spec(self.pid, 'other', 'AC-001 other', 'sandbox', [], [])
        self.store.approve_spec(self.pid, other['id'], other['sha256'], other['revision'], 'fixture')
        with self.assertRaises(Conflict):
            service.start(self.pid, other['id'])
        service.cancel(self.pid, run['id'])
        self.join(service, run['id'])

    def test_close_preserves_interrupted_and_joins_owned_workers(self):
        self.approve()
        entered = Event()
        def planner(spec, stop, rid):
            entered.set()
            stop.wait(5)
            return PLAN
        service = self.service(planner)
        run = service.start(self.pid, self.sid)
        self.assertTrue(entered.wait(3))
        service.close()
        self.services.remove(service)
        self.assertEqual('interrupted', service.status(self.pid, run['id'])['status'])
        self.assertEqual({}, service._workers)


if __name__ == '__main__':
    unittest.main()

