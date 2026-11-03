import tempfile
import unittest
from pathlib import Path
import yaml
from docloop.workflow import Workflow
from docloop.governance import GateError


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def start(self, scenario='success', mode='demo'):
        with Workflow(self.root) as flow:
            result = flow.start('demo-1', '# Demo\nAC-001: verify output\n', scenario, mode)
        self.assertIn('__interrupt__', result)

    def test_pause_restart_approve_and_archive(self):
        self.start()
        with Workflow(self.root) as flow:
            self.assertEqual(flow.status('demo-1')['status'], 'draft')
            digest = flow.gov.digest('demo-1')
            result = flow.approve('demo-1', digest, 'test-user')
        self.assertEqual(result['status'], 'accepted')
        self.assertEqual(result['history'], ['draft', 'ready', 'in_progress', 'implemented', 'verified', 'accepted'])
        archive = self.root / '文档/变更记录/demo-1'
        self.assertTrue((archive / 'manifest.yaml').is_file())
        report = yaml.safe_load((archive / 'evidence.yaml').read_text(encoding='utf-8'))
        self.assertEqual(report['verification']['mode'], 'demo')

    def test_optional_final_acceptance_requires_user_and_archives_after_decision(self):
        with Workflow(self.root, require_final_acceptance=True) as flow:
            self.assertIn('__interrupt__', flow.start('demo-accept', '# Demo\nAC-001: verify\n',
                                                      'success', 'demo'))
        with Workflow(self.root, require_final_acceptance=True) as flow:
            waiting = flow.approve('demo-accept', flow.gov.digest('demo-accept'), 'test-user')
            self.assertEqual(waiting['status'], 'awaiting_acceptance')
            self.assertEqual(waiting['review']['status'], 'passed')
            self.assertFalse((self.root / '文档/变更记录/demo-accept').exists())
            with self.assertRaises(GateError):
                flow.accept('demo-accept', '')
        with Workflow(self.root, require_final_acceptance=True) as flow:
            accepted = flow.accept('demo-accept', '最终验收人', '实际核对通过')
        self.assertEqual(accepted['status'], 'accepted')
        self.assertEqual(accepted['acceptance']['approver'], '最终验收人')
        self.assertTrue((self.root / '文档/变更记录/demo-accept/manifest.yaml').is_file())

    def test_failed_verification_never_reviews_or_archives(self):
        self.start('verification-failure')
        with Workflow(self.root) as flow:
            result = flow.approve('demo-1', flow.gov.digest('demo-1'), 'test-user')
        self.assertEqual(result['status'], 'blocked')
        self.assertNotIn('verified', result['history'])
        self.assertFalse((self.root / '文档/变更记录/demo-1').exists())
        self.assertTrue((self.root / '.docloop/recovery/demo-1.json').is_file())

    def test_stale_hash_and_real_adapter_fail_closed(self):
        self.start(mode='real')
        with Workflow(self.root) as flow:
            with self.assertRaises(GateError):
                flow.approve('demo-1', 'stale', 'test-user')
            result = flow.approve('demo-1', flow.gov.digest('demo-1'), 'test-user')
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('adapter', result['error'].lower())

    def test_resume_does_not_restart_terminal_run(self):
        self.start()
        with Workflow(self.root) as flow:
            flow.approve('demo-1', flow.gov.digest('demo-1'), 'test-user')
            with self.assertRaises(GateError):
                flow.resume('demo-1')

    def test_explicit_recovery_preserves_approval_and_resumes_failed_stage(self):
        self.start('verification-failure')
        with Workflow(self.root) as flow:
            failed = flow.approve('demo-1', flow.gov.digest('demo-1'), 'test-user')
            self.assertEqual(failed['status'], 'blocked')
        # 外部故障由操作者修复；验证节点必须复测，而不是重跑实现覆盖修复。
        sandbox = self.root / '.docloop/sessions/demo-1'
        (sandbox / 'result.json').write_text('{"mode":"demo","value":42}', encoding='utf-8')
        import subprocess
        subprocess.run(['git', 'add', 'result.json'], cwd=sandbox, check=True, capture_output=True)
        subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@localhost',
                        'commit', '-m', 'fix controlled artifact'], cwd=sandbox, check=True, capture_output=True)
        # Commit 已变更，原证据身份不可继续使用。
        with Workflow(self.root) as flow:
            recovered = flow.recover('demo-1')
        self.assertEqual(recovered['status'], 'blocked')
        self.assertIn('Commit changed', recovered['error'])

    def test_budget_survives_new_workflow_instance(self):
        self.start()
        from docloop.reliability import Limits
        with Workflow(self.root, Limits(tools=1)) as flow:
            result = flow.approve('demo-1', flow.gov.digest('demo-1'), 'test-user')
        self.assertEqual(result['status'], 'blocked')
        with Workflow(self.root, Limits(tools=1)) as flow:
            result = flow.recover('demo-1')
            self.assertEqual(result['status'], 'blocked')
            self.assertEqual(flow.reliability.usage['tools'], 1)

    def test_approval_recomputes_acceptance_ids_from_reviewed_spec(self):
        self.start()
        path = self.root / '.docloop/changes/demo-1/spec.md'
        path.write_text('# edited\nAC-001: first\nAC-002: second\n', encoding='utf-8')
        with Workflow(self.root) as flow:
            result = flow.approve('demo-1', flow.gov.digest('demo-1'), 'test-user')
        self.assertEqual(result['acceptance_ids'], ['AC-001', 'AC-002'])
        covered = [item['requirement_ids'] for item in result['evidence']['checks']]
        self.assertEqual(covered, [['AC-001'], ['AC-002']])

    def test_uncommitted_repair_cannot_validate_against_old_commit(self):
        self.start('verification-failure')
        with Workflow(self.root) as flow:
            flow.approve('demo-1', flow.gov.digest('demo-1'), 'test-user')
        sandbox = self.root / '.docloop/sessions/demo-1'
        (sandbox / 'result.json').write_text('{"mode":"demo","value":42}', encoding='utf-8')
        with Workflow(self.root) as flow:
            result = flow.recover('demo-1')
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('worktree', result['error'].lower())
        self.assertFalse((self.root / '文档/变更记录/demo-1').exists())

    def test_human_approval_wait_does_not_consume_execution_budget(self):
        with Workflow(self.root) as flow:
            flow.start('wait-1', 'AC-001: output=42', mode='demo')
            flow.reliability.started -= 4000
            flow.reliability.task_started -= 4000
            result = flow.approve('wait-1', flow.gov.digest('wait-1'), 'test-user')
        self.assertEqual(result['status'], 'accepted')

    def test_programmatic_start_requires_explicit_demo_mode(self):
        with Workflow(self.root) as flow:
            flow.start('real-1', 'AC-001: real business behavior')
            result = flow.approve('real-1', flow.gov.digest('real-1'), 'test-user')
        self.assertEqual(result['mode'], 'real')
        self.assertEqual(result['status'], 'blocked')
