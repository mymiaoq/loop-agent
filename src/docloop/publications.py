"""不可变正式产物发布；业务仓库工作区与运行状态保持独立。"""
import json
import os
import re
import time
from pathlib import Path
from uuid import uuid4
from . import deliverables
from .execution_lock import run_lock
from .execution_preparation import ExecutionPreparation
from .governance import sha256
from .workbench_store import NotFound, now
from .worktree_runtime import git as _git, safe_path, WorktreeError

# 只收录明确正式文档；轨迹、恢复状态、模型输入与来源原文不进入发布。
FORMAL_NAMES = frozenset({'spec.md', 'decisions.md', 'tasks.md', 'checkList.md',
    'evidence.yaml', 'review.yaml', 'approval.json', 'manifest.yaml',
    'verification.txt', 'plan.json', 'preparation.json', 'run-summary.json', 'difference-report.json'})


def git(repo, *args):
    try:
        return _git(repo, *args)
    except WorktreeError:
        raise WorktreeError("Git操作失败，请检查本地仓库、远端和权限；详细路径不对外返回。") from None


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def _save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(_json(value))
            stream.flush()
            os.fsync(stream.fileno())
        # Windows读者短暂占用共享删除句柄时，原子替换作有界重试。
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.02)
    finally:
        temporary.unlink(missing_ok=True)


class PublicationService:
    """冻结与上传分离；上传失败重用相同 commit 和 tag。"""
    def __init__(self, store):
        self.store = store

    def _context(self, project_id, spec_id):
        self.store.spec(project_id, spec_id)
        binding = ExecutionPreparation(self.store).binding(project_id)
        if not binding:
            raise ValueError('请先登记当前项目的本地Git仓库。')
        repo = safe_path(binding['path'])
        if safe_path(git(repo, 'rev-parse', '--show-toplevel').strip()) != repo:
            raise ValueError('登记路径不再是Git仓库根目录。')
        key = sha256((project_id + ':' + spec_id).encode())[:24]
        return repo, self.store.root / 'publications' / key

    def list(self, project_id, spec_id):
        """返回账本，不将本地提交误报为远端成功。"""
        self.store.spec(project_id, spec_id)
        key = sha256((project_id + ':' + spec_id).encode())[:24]
        root = self.store.root / 'publications' / key
        return sorted((json.loads(p.read_text(encoding='utf-8')) for p in root.glob('*/record.json')),
                      key=lambda item: item['created_at'], reverse=True)

    def _target(self, repo):
        # 只公开目标指纹；URL可能含认证信息，不写入API响应。
        try:
            remotes = git(repo, 'remote', 'get-url', '--push', '--all', 'origin').splitlines()
        except WorktreeError:
            remotes = []
        if len(remotes) > 1:
            raise ValueError('发布暂不支持多个上传目标，请登记唯一远端。')
        return {'repository': str(repo), 'origin_sha256': sha256(_json(remotes).encode())}

    def _assert_target(self, repo, record):
        if record.get('target') != self._target(repo):
            raise ValueError('发布仓库或上传目标已变更；请恢复原登记，不会自动迁移历史发布。')

    def _record(self, root, version):
        if not re.fullmatch(r'pub-[0-9a-f]{24}', version):
            raise NotFound('发布版本无效。')
        path = root / version / 'record.json'
        if not path.is_file():
            raise NotFound('发布版本不存在。')
        return path, json.loads(path.read_text(encoding='utf-8'))

    def _freeze(self, project_id, spec_id):
        data = deliverables.catalog(self.store, project_id, spec_id)
        files = {'spec.md': data['spec']['content']}
        sources = {'spec.md': 'database-spec:' + spec_id}
        for item in data['documents']:
            if item['id'] == 'spec' or item['name'] not in FORMAL_NAMES:
                continue
            # 用来源路径Hash区分同名文件；原路径写入清单，缩短Windows冻结路径。
            relative = 'artifacts/' + sha256(item['path'].encode())[:12] + '-' + item['name']
            files[relative] = deliverables.read_document(self.store, data, item)
            sources[relative] = item['path']
        if sum(len(text.encode('utf-8')) for text in files.values()) > deliverables.MAX_BUNDLE:
            raise ValueError('正式产物超过8 MiB，请缩小发布范围。')
        data['publication_sources'] = sources
        return data, files

    def publish(self, project_id, spec_id):
        """冻结当前正式材料并本地提交；不隐式上传。"""
        repo, root = self._context(project_id, spec_id)
        with run_lock(self.store.root, 'publication-' + sha256(str(repo).encode())[:24]):
            if git(repo, 'status', '--porcelain', '--untracked-files=all'):
                raise ValueError('源仓库有未提交内容，请先处理；发布不会清理或暂存现有文件。')
            data, files = self._freeze(project_id, spec_id)
            source = git(repo, 'rev-parse', 'HEAD').strip()
            entries = [{'path': path, 'source_path': data['publication_sources'][path], 'size': len(content.encode('utf-8')),
                        'sha256': sha256(content.encode('utf-8'))} for path, content in sorted(files.items())]
            identity = {'project_id': project_id, 'task_id': spec_id, 'spec_id': spec_id,
                'spec_hash': data['spec']['sha256'], 'source_code_commit': source, 'files': entries,
                'runs': [{'run_id': r['id'], 'mode': r['mode'], 'status': r['status']} for r in data['runs']]}
            version = 'pub-' + sha256(_json(identity).encode())[:24]
            path = root / version / 'record.json'
            if path.exists():
                return self._complete(repo, path, json.loads(path.read_text(encoding='utf-8')))
            previous = self.list(project_id, spec_id)
            manifest = dict(identity, version=version, created_at=now(),
                change_ids=[r['id'] for r in data['runs']], input_revision=data['spec']['revision'],
                validation_status='not_accepted', previous_version=previous[0]['version'] if previous else None)
            record = {'version': version, 'project_id': project_id, 'spec_id': spec_id,
                'created_at': manifest['created_at'], 'manifest': manifest, 'status': 'frozen',
                'branch': 'docloop-deliveries/' + root.name + '/' + version,
                'tag': 'docloop/' + root.name + '/' + version, 'commit': None,
                'remote_branch_confirmed': False, 'remote_tag_confirmed': False,
                'target': self._target(repo)}
            snapshot = path.parent / 'snapshot'
            safe_path(snapshot)
            snapshot.mkdir(parents=True, exist_ok=True)
            for relative, content in files.items():
                target = snapshot / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding='utf-8', newline='\n')
            _save(path, record)
            return self._complete(repo, path, record)

    def _reconcile_head(self, stage, path, record):
        # Git的text属性可能把原始CRLF视为工作区修改；只以提交对象核对完成状态。
        head = git(stage, 'rev-parse', 'HEAD').strip()
        source = record['manifest']['source_code_commit']
        if head == source:
            return False
        parents = git(stage, 'rev-list', '--parents', '-n', '1', head).split()
        if parents != [head, source]:
            raise ValueError('中断发布提交的代码父版本不一致，需人工核对。')
        relative = 'deliverables/' + record['version']
        manifest_file = stage / relative / 'manifest.json'
        if not manifest_file.is_file() or json.loads(manifest_file.read_text(encoding='utf-8')) != record['manifest']:
            raise ValueError('中断发布清单不一致，需人工核对。')
        files = [('manifest.json', manifest_file)]
        for item in record['manifest']['files']:
            snapshot = path.parent / 'snapshot' / item['path']
            raw = snapshot.read_bytes()
            if sha256(raw) != item['sha256'] or len(raw) != item['size']:
                raise ValueError('冻结文件校验失败，停止发布。')
            files.append((item['path'], snapshot))
        for name, frozen in files:
            blob = git(stage, 'hash-object', '--no-filters', '--', str(frozen)).strip()
            committed = git(stage, 'rev-parse', '--verify', head + ':' + relative + '/' + name).strip()
            if blob != committed:
                raise ValueError('中断发布提交与冻结材料不一致，需人工核对。')
        return True

    def _complete(self, repo, path, record):
        """持久暂存仓库保存中间提交；中断后核对同一提交再建立引用。"""
        self._assert_target(repo, record)
        stage = self.store.root / '.publication-staging' / record['version']
        stage.parent.mkdir(parents=True, exist_ok=True)
        if not stage.exists():
            git(path.parent, 'clone', '--shared', '--no-checkout', '--', str(repo), str(stage))
        if not record['commit'] and self._reconcile_head(stage, path, record):
            record['commit'] = git(stage, 'rev-parse', 'HEAD').strip()
            record['status'] = 'local_committed'
            _save(path, record)
        if not record['commit']:
            git(stage, 'checkout', '--detach', record['manifest']['source_code_commit'])
            previous = [item for item in self.list(record['project_id'], record['spec_id'])
                        if item['version'] != record['version'] and item.get('commit')]
            if previous and not (stage / 'deliverables').exists():
                git(stage, 'checkout', previous[0]['commit'], '--', 'deliverables')
            destination = stage / 'deliverables' / record['version']
            safe_path(destination)
            destination.mkdir(parents=True, exist_ok=True)
            for item in record['manifest']['files']:
                raw = (path.parent / 'snapshot' / item['path']).read_bytes()
                if sha256(raw) != item['sha256'] or len(raw) != item['size']:
                    raise ValueError('冻结文件校验失败，停止发布。')
                target = destination / item['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            _save(destination / 'manifest.json', record['manifest'])
            index = stage / '文档' / '产物版本索引.md'
            if index.parent.exists() and safe_path(index.parent) != index.parent.resolve():
                raise ValueError('版本索引目录无效。')
            safe_path(index)
            index.parent.mkdir(parents=True, exist_ok=True)
            prior = '# 产物版本索引\n\n'
            for other in self.list(record['project_id'], record['spec_id']):
                if other['version'] != record['version']:
                    prior += f"- [{other['version']}](../deliverables/{other['version']}/manifest.json) · 未验收\n"
            index.write_text(prior + f'\n- [{record["version"]}](../deliverables/{record["version"]}/manifest.json)'
                + f' · {record["manifest"]["source_code_commit"]} · 未验收\n', encoding='utf-8', newline='\n')
            # 直接按字节存入Git对象，避免autocrlf或.gitattributes改写已冻结材料。
            paths = [destination / item['path'] for item in record['manifest']['files']]
            paths.extend([destination / 'manifest.json', index])
            for item in paths:
                blob = git(stage, 'hash-object', '-w', '--no-filters', '--', str(item)).strip()
                git(stage, 'update-index', '--add', '--cacheinfo', '100644,' + blob + ',' + item.relative_to(stage).as_posix())
            git(stage, '-c', 'user.name=DocLoop', '-c', 'user.email=docloop@localhost',
                '-c', 'commit.gpgsign=false', 'commit', '-m', 'DocLoop publication ' + record['version'])
            record['commit'] = git(stage, 'rev-parse', 'HEAD').strip()
            record['status'] = 'local_committed'
            _save(path, record)
        git(repo, 'fetch', '--no-tags', '--', str(stage), record['commit'])
        branch_ref = 'refs/heads/' + record['branch']
        refs = git(repo, 'for-each-ref', '--format=%(objectname)', branch_ref).strip()
        if refs and refs != record['commit']:
            raise ValueError('发布分支冲突，需人工核对。')
        if not refs:
            git(repo, 'update-ref', branch_ref, record['commit'], '0' * len(record['commit']))
        tags = git(repo, 'tag', '--list', record['tag']).strip()
        if tags:
            if git(repo, 'rev-parse', record['tag'] + '^{}').strip() != record['commit']:
                raise ValueError('发布标签冲突，需人工核对。')
        else:
            git(repo, '-c', 'user.name=DocLoop', '-c', 'user.email=docloop@localhost',
                '-c', 'tag.gpgsign=false', 'tag', '-a', record['tag'], record['commit'],
                '-m', 'DocLoop immutable publication ' + record['version'])
        if record['status'] in {'frozen', 'local_committed'}:
            record['status'] = 'pending_upload'
            _save(path, record)
        return record

    def sync(self, project_id, spec_id, version):
        """仅推送专用分支与标签，逐项核验远端引用。"""
        repo, root = self._context(project_id, spec_id)
        with run_lock(self.store.root, 'publication-' + sha256(str(repo).encode())[:24]):
            path, record = self._record(root, version)
            record = self._complete(repo, path, record)
            record['remote_branch_confirmed'] = False
            record['remote_tag_confirmed'] = False
            branch, tag = 'refs/heads/' + record['branch'], 'refs/tags/' + record['tag']
            try:
                # 不强推；分支成功、标签失败时仍保留可重试的相同版本。
                for ref in (branch, tag):
                    git(repo, 'push', '--porcelain', 'origin', ref + ':' + ref)
                remote = git(repo, 'ls-remote', git(repo, 'remote', 'get-url', '--push', 'origin').strip(), branch, tag, tag + '^{}')
                refs = dict(line.split('\t', 1)[::-1] for line in remote.splitlines() if '\t' in line)
                record['remote_branch_confirmed'] = refs.get(branch) == record['commit']
                record['remote_tag_confirmed'] = refs.get(tag + '^{}') == record['commit']
                if not all(record[k] for k in ('remote_branch_confirmed', 'remote_tag_confirmed')):
                    raise ValueError('远端引用尚未确认。')
                record['status'] = 'remote_confirmed'
                record.pop('error', None)
                record.pop('remote_check_status', None)
            except (WorktreeError, ValueError):
                try:
                    remote = git(repo, 'ls-remote', git(repo, 'remote', 'get-url', '--push', 'origin').strip(), branch, tag, tag + '^{}')
                    refs = dict(line.split('\t', 1)[::-1] for line in remote.splitlines() if '\t' in line)
                    record['remote_branch_confirmed'] = refs.get(branch) == record['commit']
                    record['remote_tag_confirmed'] = refs.get(tag + '^{}') == record['commit']
                except WorktreeError:
                    record['remote_check_status'] = 'unavailable'
                record['status'] = 'upload_failed'
                record['error'] = '上传或远端核验失败；请检查远端和权限后重试同一版本。'
            _save(path, record)
            return record

    def document(self, project_id, spec_id, version, path):
        """只读取清单允许的冻结版本，校验内容后返回UTF-8文档。"""
        repo, root = self._context(project_id, spec_id)
        _, record = self._record(root, version)
        self._assert_target(repo, record)
        entry = next((item for item in record['manifest']['files'] if item['path'] == path), None)
        if path not in {'manifest.json', 'version-index'} and entry is None:
            raise NotFound('此发布中没有该文档。')
        if not record['commit']:
            raise ValueError('发布尚未提交，请重试发布。')
        relative = '文档/产物版本索引.md' if path == 'version-index' else 'deliverables/' + version + '/' + path
        # 用Git对象Hash核对本地冻结原字节，避免text模式stdout的换行转换。
        frozen = (self.store.root / '.publication-staging' / version) if path in {'version-index', 'manifest.json'} else root / version / 'snapshot'
        frozen = frozen / (relative if path in {'version-index', 'manifest.json'} else path)
        safe_path(frozen)
        blob = git(repo, 'rev-parse', record['commit'] + ':' + relative).strip()
        local_blob = git(repo, 'hash-object', '--no-filters', '--', str(frozen)).strip()
        if blob != local_blob:
            raise ValueError('发布内容校验失败。')
        content = frozen.read_bytes().decode('utf-8')
        if entry and sha256(content.encode('utf-8')) != entry['sha256']:
            raise ValueError('发布内容校验失败。')
        return {'name': Path(path).name, 'path': path, 'version': version, 'content': content,
                'sha256': sha256(content.encode('utf-8'))}
