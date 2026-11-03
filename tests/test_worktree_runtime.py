import tempfile
import unittest
import subprocess
from pathlib import Path
from docloop.worktree_runtime import WorktreeRuntime, WorktreeError


class WorktreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd().anchor)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        self.git('init')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        (self.repo / 'file.txt').write_text('base\n')
        self.git('add', '.')
        self.git('commit', '-m', 'fixture')
        self.commit = self.git('rev-parse', 'HEAD').strip()
        self.runtime = WorktreeRuntime([self.repo])
        self.args = dict(repository_path=self.repo, baseline_commit=self.commit,
                         run_id='run-1', worktree_root=self.base / 'trees',
                         approved_spec_hash='a' * 64)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              capture_output=True, text=True, timeout=20).stdout

    def test_preparation_does_not_run_checkout_hooks(self):
        marker = self.base / 'hook-ran.txt'
        hook = self.repo / '.git/hooks/post-checkout'
        hook.write_bytes(('#!/bin/sh\necho triggered > "' + marker.as_posix() + '"\n').encode())
        hook.chmod(0o755)
        self.runtime.prepare(**self.args)
        self.assertFalse(marker.exists(), 'Checkout hook executed outside isolation')

    def test_preparation_disables_checkout_filters(self):
        marker = self.base / 'filter-ran.txt'
        (self.repo / '.gitattributes').write_bytes(b'*.txt filter=fixture\n')
        self.git('add', '.gitattributes')
        self.git('commit', '-m', 'attributes')
        self.args['baseline_commit'] = self.git('rev-parse', 'HEAD').strip()
        self.git('config', 'filter.fixture.smudge', 'echo triggered > "' + marker.as_posix() + '"; cat')
        self.runtime.prepare(**self.args)
        self.assertFalse(marker.exists(), 'Checkout filter executed outside isolation')

    def test_prepare_and_reuse_preserves_changes(self):
        result = self.runtime.prepare(**self.args)
        path = Path(result['path'])
        self.assertEqual(result['branch'], 'docloop/run-1')
        self.assertEqual(result['basecommit'], self.commit)
        self.assertFalse(self.runtime.snapshot(**self.args)['dirty'])
        (path / 'file.txt').write_text('edited\n')
        (path / 'new.txt').write_text('untracked')
        self.assertEqual(self.runtime.prepare(**self.args), result)
        snapshot = self.runtime.snapshot(**self.args)
        self.assertTrue(snapshot['dirty'])
        self.assertIn('+edited', snapshot['diff'])
        self.assertIn('new.txt', snapshot['status'])
        self.assertFalse(self.git('status', '--porcelain'))

    def test_rejects_unregistered_and_dirty(self):
        with self.assertRaises(WorktreeError):
            WorktreeRuntime([]).prepare(**self.args)
        (self.repo / 'untracked').write_text('preserve')
        with self.assertRaises(WorktreeError):
            self.runtime.prepare(**self.args)

    def test_rejects_invalid_inputs(self):
        for change in [dict(run_id='../escape'), dict(approved_spec_hash='bad'),
                       dict(baseline_commit='f'*40), dict(worktree_root=self.repo / 'trees'),
                       dict(worktree_root=Path.home() / 'trees')]:
            with self.subTest(change=change), self.assertRaises(WorktreeError):
                self.runtime.prepare(**(self.args | change))

    def test_rejects_changed_baseline_and_manifest(self):
        self.runtime.prepare(**self.args)
        with self.assertRaises(WorktreeError):
            self.runtime.prepare(**(self.args | dict(approved_spec_hash='b'*64)))
        (self.repo / 'file.txt').write_text('next')
        self.git('add', '.')
        self.git('commit', '-m', 'next')
        with self.assertRaises(WorktreeError):
            self.runtime.prepare(**self.args)

    def test_refuses_existing_directory_and_branch(self):
        target = self.args['worktree_root'] / 'run-1'
        target.mkdir(parents=True)
        (target / 'keep').write_text('user')
        with self.assertRaises(WorktreeError):
            self.runtime.prepare(**self.args)
        self.assertEqual((target / 'keep').read_text(), 'user')

    def test_rejects_non_git(self):
        other = self.base / 'other'
        other.mkdir()
        with self.assertRaises(WorktreeError):
            WorktreeRuntime([other]).prepare(**(self.args | dict(repository_path=other)))




    def test_existing_branch_without_manifest_is_rejected(self):
        self.git('branch', 'docloop/run-1')
        with self.assertRaises(WorktreeError):
            self.runtime.prepare(**self.args)

    def test_linked_root_is_rejected(self):
        target = self.base / 'real'
        target.mkdir()
        link = self.base / 'link'
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest('Windows symlink privilege unavailable')
        with self.assertRaises(WorktreeError):
            self.runtime.prepare(**(self.args | dict(worktree_root=link / 'trees')))

    def test_traversal_root_is_rejected(self):
        with self.assertRaises(WorktreeError):
            self.runtime.prepare(**(self.args | dict(worktree_root=self.base / '..' / 'escape')))


    def test_snapshot_survives_source_changes(self):
        result = self.runtime.prepare(**self.args)
        (Path(result['path']) / 'file.txt').write_text('cancelled edit')
        (self.repo / 'source-untracked').write_text('source edit')
        snapshot = self.runtime.snapshot(**self.args)
        self.assertTrue(snapshot['dirty'])
        self.assertIn('+cancelled edit', snapshot['diff'])

