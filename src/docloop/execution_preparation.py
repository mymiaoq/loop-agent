"""P0执行准备：显式仓库登记、批准基线绑定和Worktree，不运行生成代码。"""
import json
import os
import shutil
import subprocess
from uuid import uuid4
from .execution_lock import run_lock
from .governance import sha256, write_json
from .operations import OperationLedger
from .worktree_runtime import WorktreeRuntime, WorktreeError, safe_path, git


def docker_ready():
    binary = shutil.which('docker')
    if not binary:
        return False
    try:
        options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        result = subprocess.run([binary, 'info', '--format', '{{.ServerVersion}}'],
            capture_output=True, timeout=5, **options)
        return result.returncode == 0 and bool(result.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        return False


class ExecutionPreparation:
    def __init__(self, store):
        self.store = store

    def _path(self, project_id):
        self.store.specs(project_id)  # 先验证项目存在，不用客户端路径拼接读取其他目录。
        return self.store.root / '.settings/repositories' / (project_id + '.json')

    def binding(self, project_id):
        path = self._path(project_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            raise ValueError('本地仓库配置无法读取，请重新登记。') from None

    def register(self, project_id, repository):
        path = self._path(project_id)
        if not os.path.isabs(repository):
            raise WorktreeError('请输入本地Git仓库的绝对路径。')
        repo = safe_path(repository)
        if safe_path(git(repo, 'rev-parse', '--show-toplevel').strip()) != repo:
            raise WorktreeError('必须选择Git仓库根目录。')
        if git(repo, 'status', '--porcelain', '--untracked-files=all'):
            raise WorktreeError('源仓库有未提交内容，请先保留并处理；不会自动清理或覆盖。')
        binding = {'path': str(repo), 'baseline_commit': git(repo, 'rev-parse', 'HEAD').strip()}
        temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
        try:
            write_json(temporary, binding, exclusive=True)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return binding

    def prepare(self, project_id, spec_id):
        raw = self.store.approved_bytes(project_id, spec_id)
        binding = self.binding(project_id)
        if not binding:
            raise WorktreeError('请先在设置中登记当前项目的本地Git仓库。')
        spec_hash = sha256(raw)
        identity = json.dumps([project_id, spec_id, spec_hash, binding], sort_keys=True)
        run_id = 'prep-' + sha256(identity.encode())[:24]
        runtime = WorktreeRuntime([binding['path']])
        arguments = dict(repository_path=binding['path'], baseline_commit=binding['baseline_commit'],
            run_id=run_id, worktree_root=self.store.root / 'worktrees' / project_id,
            approved_spec_hash=spec_hash)
        ledger = OperationLedger(self.store.root, run_id)
        operation = ledger.begin('worktree:prepare', 'worktree', {
            'repository': binding['path'], 'baseline_commit': binding['baseline_commit'],
            'spec_hash': spec_hash})
        try:
            with run_lock(self.store.root, run_id):
                worktree = runtime.prepare(**arguments)
                snapshot = runtime.snapshot(**arguments)
        except Exception as error:
            if operation['status'] != 'completed':
                ledger.fail('worktree:prepare', type(error).__name__)
            raise
        if operation['status'] != 'completed':
            ledger.complete('worktree:prepare', {'path': worktree['path'], 'branch': worktree['branch']})
        docker = docker_ready()
        return {'status': 'prepared', 'worktree': worktree, 'snapshot': snapshot,
                'docker_ready': docker, 'business_code_execution': False, 'execution_gate': 'blocked',
                'reason': '工作区准备完成；真实编码执行器及权限门禁尚未启用。' if docker else
                          '工作区准备完成；Docker引擎不可用，未执行生成代码。'}
