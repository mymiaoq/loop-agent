import json
import tempfile
import unittest
import subprocess
import sys
import time
from pathlib import Path
from threading import Event

from docloop.managed_runs import ManagedRuns
from docloop.workbench_store import WorkbenchStore, Conflict
from test_managed_runs import PLAN, Prep


class DurableRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = WorkbenchStore.sandbox(Path(self.temp.name))
        self.pid = self.store.create_project('durable')['id']
        spec = self.store.create_spec(self.pid, 'task', 'AC-001 功能', 'sandbox', [], [])
        self.sid = spec['id']
        self.store.approve_spec(self.pid, self.sid, spec['sha256'], 1, 'tester')
        self.prep = Prep()
        self.services = []

    def tearDown(self):
        for service in self.services:
            service.close()
        self.store.close()
        self.temp.cleanup()

    def service(self, planner):
        value = ManagedRuns(self.store, self.prep, planner)
        self.services.append(value)
        return value

    def test_pause_keeps_completed_plan_then_resume_same_run_without_model_repeat(self):
        entered, release = Event(), Event()
        calls = []
        def planner(spec, stop, rid):
            calls.append(rid)
            entered.set()
            release.wait(3)
            return PLAN
        service = self.service(planner)
        run = service.start(self.pid, self.sid)
        self.assertTrue(entered.wait(3))
        service.pause(self.pid, run['id'])
        release.set()
        paused = service.wait(self.pid, run['id'], 5)
        self.assertEqual('paused', paused['status'])
        self.assertEqual([], self.prep.calls)
        self.assertEqual(run['id'], service.start(self.pid, self.sid)['id'])
        service.resume(self.pid, run['id'])
        result = service.wait(self.pid, run['id'], 5)
        self.assertEqual('blocked', result['status'])
        self.assertEqual([run['id']], calls)
        self.assertEqual(1, len(self.prep.calls))
        self.assertEqual(1, len(self.store.task_runs(self.pid, self.sid)))

    def test_restart_recovers_same_checkpoint_and_cancelled_run_cannot_resume(self):
        entered = Event()
        def planner(spec, stop, rid):
            entered.set()
            stop.wait(3)
            raise RuntimeError('request interrupted')
        first = self.service(planner)
        run = first.start(self.pid, self.sid)
        self.assertTrue(entered.wait(3))
        first.close()
        self.services.remove(first)
        self.assertEqual('interrupted', self.store.run(self.pid, run['id'])['status'])
        second = self.service(lambda *args: PLAN)
        second.resume(self.pid, run['id'])
        self.assertEqual('blocked', second.wait(self.pid, run['id'], 5)['status'])
        second.close()
        self.services.remove(second)

    def test_paused_cancel_and_input_tampering_are_guarded(self):
        entered = Event()
        def planner(spec, stop, rid):
            entered.set()
            stop.wait(3)
            return PLAN
        service = self.service(planner)
        run = service.start(self.pid, self.sid)
        self.assertTrue(entered.wait(3))
        service.pause(self.pid, run['id'])
        service.wait(self.pid, run['id'], 5)
        folder = self.store.root / 'runs' / run['id']
        snapshot = folder / 'run-input.json'
        data = json.loads(snapshot.read_text(encoding='utf-8'))
        data['spec_hash'] = '0' * 64
        snapshot.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(Conflict):
            service.resume(self.pid, run['id'])
        service.cancel(self.pid, run['id'])
        self.assertEqual('cancelled', self.store.run(self.pid, run['id'])['status'])
        with self.assertRaises(Conflict):
            service.resume(self.pid, run['id'])

    def test_persisted_cancel_wins_over_crash_recovery(self):
        run = self.store.start_run(self.pid, self.sid, mode='runtime')
        folder = self.store.root / 'runs' / run['id']
        folder.mkdir(parents=True)
        (folder / 'run-input.json').write_text('{}')
        self.store.request_cancel(self.pid, run['id'])
        self.store.recover_interrupted_runs()
        self.assertEqual('cancelled', self.store.run(self.pid, run['id'])['status'])

    def test_killed_process_recovers_original_run_from_disk(self):
        code = '''
import sys
from pathlib import Path
from docloop.workbench_store import WorkbenchStore
from docloop.managed_runs import ManagedRuns
root, pid, sid = sys.argv[1:]
store = WorkbenchStore.sandbox(Path(root))
class Preparation:
    def prepare(self, *args): return {}
def planner(spec, signal, rid):
    (Path(root) / 'entered.txt').write_text(rid)
    signal.wait(60)
service = ManagedRuns(store, Preparation(), planner)
run = service.start(pid, sid)
service.wait(pid, run['id'], 60)
'''
        worker = subprocess.Popen([sys.executable, '-c', code, str(self.store.root), self.pid, self.sid],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            marker = self.store.root / 'entered.txt'
            deadline = time.monotonic() + 8
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(.05)
            self.assertTrue(marker.is_file())
            rid = marker.read_text()
            self.kill_worker(worker)
            worker.wait(timeout=5)
            service = self.service(lambda *args: PLAN)
            self.assertEqual('interrupted', service.status(self.pid, rid)['status'])
            service.resume(self.pid, rid)
            self.assertEqual('blocked', service.wait(self.pid, rid, 5)['status'])
            self.assertEqual(1, len(self.store.task_runs(self.pid, self.sid)))
        finally:
            if worker.poll() is None:
                self.kill_worker(worker)
                worker.wait(timeout=5)

    @staticmethod
    def kill_worker(worker):
        import os
        if os.name == 'nt':
            # uv的venv入口可能转发给子Python；只杀入口会留下持锁的真正Worker。
            subprocess.run(['taskkill', '/PID', str(worker.pid), '/T', '/F'],
                           capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            worker.kill()
