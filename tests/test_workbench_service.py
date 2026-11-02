import tempfile
import unittest
from pathlib import Path
from docloop.workbench_store import WorkbenchStore, Conflict
from docloop.workbench_service import WorkbenchService
from docloop.model_gateway import ModelUnavailable

ROOT = Path(__file__).resolve().parents[1]


class WorkbenchServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = WorkbenchStore.sandbox(Path(self.tmp.name))
        self.addCleanup(self.store.close)
        self.service = WorkbenchService(ROOT, self.store)
        self.pid = self.store.create_project('独立沙箱')['id']

    def test_sandbox_generation_reads_local_skills_and_pins_sources(self):
        self.store.import_document(self.pid, '需求.md', '资料导入后需要审批并保留来源。'.encode())
        spec = self.service.generate_spec(self.pid, '资料审批', '实现资料导入和审批', 'sandbox')
        self.assertEqual(spec['generation_mode'], 'sandbox')
        self.assertIn('AC-001', spec['content'])
        self.assertTrue(spec['references'])
        refs = {item['ref'] for item in spec['skill_sources']}
        self.assertIn('superpowers:brainstorming', refs)
        self.assertTrue((Path(self.tmp.name) / 'inputs').is_dir())

    def test_unconfigured_real_generation_refuses_to_simulate(self):
        with self.assertRaises(ModelUnavailable):
            self.service.generate_spec(self.pid, '真实', '真实需求', 'real')
        self.assertEqual(self.store.specs(self.pid), [])

    def test_snapshot_hash_covers_final_model_input(self):
        import json
        from docloop.governance import sha256
        self.service.generate_spec(self.pid, '输入证据', '检查来源', 'sandbox')
        snapshot = next((Path(self.tmp.name) / 'inputs').glob('*.json'))
        packet = json.loads(snapshot.read_text(encoding='utf-8'))
        recorded = packet.pop('input_sha256')
        self.assertEqual(recorded, sha256(json.dumps(packet, ensure_ascii=False, sort_keys=True).encode('utf-8')))

    def test_run_requires_approval_and_failure_stays_blocked(self):
        spec = self.service.generate_spec(self.pid, '沙箱', '验证审批门禁', 'sandbox')
        with self.assertRaises(Conflict):
            self.service.run_demo(self.pid, spec['id'])
        self.store.approve_spec(self.pid, spec['id'], spec['sha256'], spec['revision'], '测试者')
        run = self.service.run_demo(self.pid, spec['id'], 'verification-failure')
        self.assertEqual(run['status'], 'blocked')
        self.assertEqual(run['mode'], 'demo')
        ok = self.service.run_demo(self.pid, spec['id'], 'success')
        self.assertEqual(ok['status'], 'accepted')
        self.assertTrue(ok['result']['history'])
