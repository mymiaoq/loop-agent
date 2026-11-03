import tempfile
import unittest
from pathlib import Path
from threading import Event
from docloop.workbench_store import WorkbenchStore, Conflict
from docloop.workbench_service import WorkbenchService

ROOT = Path(__file__).resolve().parents[1]


class BackgroundAnalysisTests(unittest.TestCase):
    def test_analysis_has_identity_before_model_returns_and_survives_refresh_pause(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkbenchStore.sandbox(Path(directory))
            service = WorkbenchService(ROOT, store)
            pid = store.create_project('test')['id']
            entered = Event()
            class Gateway:
                def complete(self, messages, *, cancel_event=None):
                    entered.set()
                    cancel_event.wait(3)
                    raise RuntimeError('stopped')
                def cancel_all(self):
                    pass
            service.gateway = Gateway()
            try:
                task = service.start_analysis(pid, '新任务', '生成规格', 'real', 'request-1')
                self.assertTrue(entered.wait(3))
                again = service.start_analysis(pid, '新任务', '生成规格', 'real', 'request-1')
                self.assertEqual(task['id'], again['id'])
                run = store.task_runs(pid, task['id'])[0]
                with self.assertRaises(Conflict):
                    current = store.spec(pid, task['id'])
                    store.approve_spec(pid, task['id'], current['sha256'], current['revision'], 'tester')
                service.runtime().pause(pid, run['id'])
                self.assertEqual('paused', service.runtime().wait(pid, run['id'], 5)['status'])
                self.assertEqual('draft', store.spec(pid, task['id'])['status'])
                service.runtime().cancel(pid, run['id'])
                self.assertEqual('cancelled', store.run(pid, run['id'])['status'])
            finally:
                service.close()
                store.close()

    def test_sandbox_background_analysis_updates_existing_spec_once(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkbenchStore.sandbox(Path(directory))
            service = WorkbenchService(ROOT, store)
            pid = store.create_project('test')['id']
            try:
                task = service.start_analysis(pid, '任务', '需要导出', 'sandbox', 'sandbox-1')
                run = store.task_runs(pid, task['id'])[0]
                self.assertEqual('succeeded', service.runtime().wait(pid, run['id'], 5)['status'])
                spec = store.spec(pid, task['id'])
                self.assertIn('需要导出', spec['content'])
                self.assertNotIn('分析正在进行', spec['content'])
                self.assertEqual(1, len(store.specs(pid)))
                self.assertEqual(task['id'], service.start_analysis(pid, '任务', '需要导出', 'sandbox', 'sandbox-1')['id'])
            finally:
                service.close()
                store.close()

    def test_transient_analysis_failure_can_retry_same_run(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkbenchStore.sandbox(Path(directory))
            service = WorkbenchService(ROOT, store)
            pid = store.create_project('retry')['id']
            class Gateway:
                calls = 0
                def complete(self, messages, *, cancel_event=None):
                    self.calls += 1
                    if self.calls == 1:
                        raise RuntimeError('temporary')
                    return {'content': 'AC-001 重试后的需求', 'model': 'fixture', 'usage': {}}
                def cancel_all(self):
                    pass
            service.gateway = Gateway()
            try:
                task = service.start_analysis(pid, '任务', '需要重试', 'real', 'retry-1')
                run = store.task_runs(pid, task['id'])[0]
                self.assertEqual('blocked', service.runtime().wait(pid, run['id'], 5)['status'])
                from unittest.mock import patch
                with patch('docloop.workbench_service.SkillRegistry', side_effect=RuntimeError('changed local skills')):
                    service.runtime().resume(pid, run['id'])
                    self.assertEqual('succeeded', service.runtime().wait(pid, run['id'], 5)['status'])
                self.assertEqual(1, len(store.task_runs(pid, task['id'])))
                self.assertEqual('AC-001 重试后的需求', store.spec(pid, task['id'])['content'])
            finally:
                service.close()
                store.close()
