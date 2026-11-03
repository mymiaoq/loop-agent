import tempfile
import unittest
from pathlib import Path
from threading import Event
from docloop.workbench_store import WorkbenchStore, Conflict, NotFound
from docloop.workbench_service import WorkbenchService

ROOT = Path(__file__).resolve().parents[1]


class TaskUpdateTests(unittest.TestCase):
    def test_upload_pauses_original_and_creates_reviewable_change_without_mutating_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkbenchStore.sandbox(Path(directory))
            service = WorkbenchService(ROOT, store)
            pid = store.create_project('fixture')['id']
            spec = store.create_spec(pid, '旧需求', 'AC-001 支持查看', 'sandbox', [], [])
            store.approve_spec(pid, spec['id'], spec['sha256'], 1, 'tester')
            original = store.approved_bytes(pid, spec['id'])
            entered = Event()
            def planner(spec, stop, rid):
                entered.set()
                stop.wait(3)
                raise RuntimeError('paused')
            runtime = service.runtime()
            runtime.plan_builder = planner
            try:
                run = runtime.start(pid, spec['id'])
                self.assertTrue(entered.wait(3))
                update = service.updates().submit(pid, spec['id'], '新增.md', 'AC-002 增加导出'.encode(), 'sandbox')
                result = service.updates().wait(pid, spec['id'], update['id'], 5)
                self.assertEqual('waiting_confirmation', result['status'])
                self.assertEqual('paused', store.run(pid, run['id'])['status'])
                new = store.spec(pid, result['new_spec_id'])
                self.assertEqual('draft', new['status'])
                self.assertIn('导出', new['content'])
                self.assertIn('新增', result['report'])
                self.assertIn('未确认', result['report'])
                self.assertEqual(original, store.approved_bytes(pid, spec['id']))
                self.assertEqual('succeeded', store.task_runs(pid, new['id'])[0]['status'])
                with self.assertRaises(Conflict):
                    runtime.resume(pid, run['id'])
                other = store.create_project('other')['id']
                with self.assertRaises(NotFound):
                    service.updates().list(other, spec['id'])
                # 模拟审批已提交、批次账本更新前进程退出；新服务根据批准记录对账。
                store.approve_spec(pid, new['id'], new['sha256'], new['revision'], 'tester')
                from docloop.task_updates import TaskUpdates
                recovered = TaskUpdates(service)
                self.assertEqual('applied', recovered.get(pid, spec['id'], update['id'])['status'])
                self.assertEqual('superseded', store.run(pid, run['id'])['status'])
            finally:
                service.close()
                store.close()
