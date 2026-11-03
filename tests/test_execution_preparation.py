import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from docloop.execution_preparation import ExecutionPreparation
from docloop.workbench_store import WorkbenchStore, Conflict


class ExecutionPreparationTests(unittest.TestCase):
    def test_preparation_requires_approval_and_never_claims_business_execution(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd().anchor) as tmp:
            root = Path(tmp)
            repo = root / 'repo'
            repo.mkdir()
            def git(*args):
                subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, timeout=20)
            git('init')
            git('-c', 'user.email=fixture@local', '-c', 'user.name=fixture', 'commit', '--allow-empty', '-m', 'baseline')
            store = WorkbenchStore.sandbox(root / 'data')
            try:
                project = store.create_project('准备测试')['id']
                spec = store.create_spec(project, '需求', '# Spec\nAC-001: test', 'sandbox', [], [])
                service = ExecutionPreparation(store)
                service.register(project, str(repo))
                with self.assertRaises(Conflict):
                    service.prepare(project, spec['id'])
                store.approve_spec(project, spec['id'], spec['sha256'], 1, 'tester')
                with patch('docloop.execution_preparation.docker_ready', return_value=False):
                    result = service.prepare(project, spec['id'])
                    repeated = service.prepare(project, spec['id'])
                self.assertEqual(result['worktree'], repeated['worktree'])
                self.assertEqual(result['execution_gate'], 'blocked')
                self.assertFalse(result['business_code_execution'])
                self.assertTrue(Path(result['worktree']['path']).is_dir())
                self.assertEqual(ExecutionPreparation(store).binding(project)['path'], str(repo.resolve()))
            finally:
                store.close()
