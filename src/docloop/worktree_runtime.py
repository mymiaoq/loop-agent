"""Controlled worktree preparation; no coding, cleanup, commit or push."""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


class WorktreeError(ValueError):
    pass


def safe_path(value):
    path = Path(value).absolute()
    if '..' in path.parts:
        raise WorktreeError('Path traversal is forbidden')
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise WorktreeError('Linked paths are forbidden')
    return path.resolve()


def git(repo, *args):
    try:
        options = dict(shell=False, timeout=30, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
        if os.name == 'nt':
            options['creationflags'] = subprocess.CREATE_NO_WINDOW
        # Git准备也不得执行仓库hook、fsmonitor、checkout filter或外部diff程序。
        with tempfile.TemporaryDirectory(prefix='docloop-empty-hooks-') as hooks:
            command = ['git', '-c', 'core.hooksPath=' + hooks, '-c', 'core.fsmonitor=false',
                       '-c', 'submodule.recurse=false', '-C', str(repo)]
            config = subprocess.run([*command, 'config', '--get-regexp',
                r'^filter\..*\.(clean|smudge|process|required)$'], **options)
            if config.returncode not in {0, 1}:
                raise WorktreeError('Cannot inspect Git filter configuration')
            filters = {line.split(None, 1)[0].rsplit('.', 1)[0] for line in config.stdout.splitlines() if line}
            if len(filters) > 100:
                raise WorktreeError('Too many Git filters; inspect repository configuration')
            for name in sorted(filters):
                for kind in ('clean', 'smudge', 'process', 'required'):
                    command.extend(['-c', name + '.' + kind + '=' + ('false' if kind == 'required' else '')])
            if args and args[0] == 'diff':
                args = ('diff', '--no-ext-diff', '--no-textconv', *args[1:])
            result = subprocess.run([*command, *args], check=True, **options)
            return result.stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise WorktreeError(f'Git operation failed: {exc}') from exc


class WorktreeRuntime:
    """Registry must be supplied by trusted user configuration, never model output."""

    def __init__(self, registered_repositories):
        self.repositories = frozenset(safe_path(p) for p in registered_repositories)

    def _context(self, *, repository_path, baseline_commit, run_id,
                 worktree_root, approved_spec_hash, _check_source=True):
        repo = safe_path(repository_path)
        root = safe_path(worktree_root)
        if repo not in self.repositories:
            raise WorktreeError('Repository was not explicitly registered')
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', run_id):
            raise WorktreeError('Invalid run ID')
        if not re.fullmatch(r'[0-9a-f]{64}', approved_spec_hash):
            raise WorktreeError('Approved spec SHA256 is required')
        if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', baseline_commit):
            raise WorktreeError('Baseline must be a full immutable commit ID')
        if root.is_relative_to(repo) or repo.is_relative_to(root):
            raise WorktreeError('Worktree root overlaps source repository')
        if root.is_relative_to(Path.home().resolve()):
            raise WorktreeError('Worktree root is inside user home')
        if Path(git(repo, 'rev-parse', '--show-toplevel').strip()).resolve() != repo:
            raise WorktreeError('Repository must be its Git top-level directory')
        commit = git(repo, 'rev-parse', '--verify', baseline_commit + '^{commit}').strip()
        if commit != baseline_commit or (_check_source and git(repo, 'rev-parse', 'HEAD').strip() != commit):
            raise WorktreeError('Source baseline changed')
        if _check_source and git(repo, 'status', '--porcelain', '--untracked-files=all'):
            raise WorktreeError('Source repository is dirty')
        path = safe_path(root / run_id)
        metadata_root = safe_path(root.parent / (root.name + '.docloop-metadata'))
        if metadata_root.is_relative_to(repo):
            raise WorktreeError('Metadata overlaps source repository')
        manifest = safe_path(metadata_root / (run_id + '.json'))
        expected = dict(path=str(path), branch='docloop/' + run_id,
                        basecommit=commit, spec_hash=approved_spec_hash,
                        repository=str(repo))
        return repo, root, path, manifest, expected

    def _existing(self, repo, path, manifest, expected):
        try:
            actual = json.loads(manifest.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise WorktreeError('Invalid or missing worktree manifest') from exc
        if actual != expected or not path.is_dir():
            raise WorktreeError('Worktree identity mismatch')
        if Path(git(path, 'rev-parse', '--show-toplevel').strip()).resolve() != path:
            raise WorktreeError('Worktree path mismatch')
        common = Path(git(path, 'rev-parse', '--path-format=absolute', '--git-common-dir').strip()).resolve()
        source_common = Path(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir').strip()).resolve()
        if common != source_common:
            raise WorktreeError('Worktree repository mismatch')
        if git(path, 'symbolic-ref', '--short', 'HEAD').strip() != expected['branch']:
            raise WorktreeError('Worktree branch mismatch')
        return {k: expected[k] for k in ('path', 'branch', 'basecommit', 'spec_hash')}

    def prepare(self, **arguments):
        if '_check_source' in arguments:
            raise WorktreeError('Internal option is forbidden')
        repo, root, path, manifest, expected = self._context(**arguments)
        if manifest.exists():
            return self._existing(repo, path, manifest, expected)
        if path.exists():
            raise WorktreeError('Refusing to overwrite existing target')
        branches = git(repo, 'for-each-ref', '--format=%(refname)', 'refs/heads/' + expected['branch']).splitlines()
        if 'refs/heads/' + expected['branch'] in branches:
            raise WorktreeError('Branch already exists without matching manifest')
        root.mkdir(parents=True, exist_ok=True)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        # Reserve identity before Git mutation; a failed add requires manual inspection.
        with manifest.open('x', encoding='utf-8') as stream:
            json.dump(expected, stream, sort_keys=True)
        git(repo, 'worktree', 'add', '-b', expected['branch'], str(path), expected['basecommit'])
        return self._existing(repo, path, manifest, expected)

    def snapshot(self, **arguments):
        repo, _, path, manifest, expected = self._context(**arguments, _check_source=False)
        self._existing(repo, path, manifest, expected)
        status = git(path, 'status', '--porcelain', '--untracked-files=all')
        return dict(head=git(path, 'rev-parse', 'HEAD').strip(), dirty=bool(status),
                    status=status, diff=git(path, 'diff', 'HEAD', '--'))


