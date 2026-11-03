import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from docloop.execution_preparation import ExecutionPreparation
from docloop.workbench_store import WorkbenchStore
from docloop.publications import PublicationService


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init')
        self.git('config', 'user.name', 'fixture')
        self.git('config', 'user.email', 'fixture@local')
        self.git('commit', '--allow-empty', '-m', 'base')
        self.source = self.git('rev-parse', 'HEAD').strip()
        self.remote = self.root / 'remote.git'
        subprocess.run(['git', 'init', '--bare', str(self.remote)], check=True, capture_output=True)
        self.git('remote', 'add', 'origin', str(self.remote))
        self.store = WorkbenchStore.sandbox(self.root / 'data')
        self.project = self.store.create_project('project')['id']
        spec = self.store.create_spec(self.project, 'task', '# Spec AC-001 approved', 'sandbox', [], [])
        self.spec = spec['id']
        self.store.approve_spec(self.project, self.spec, spec['sha256'], 1, 'tester')
        ExecutionPreparation(self.store).register(self.project, str(self.repo))
        self.service = PublicationService(self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              capture_output=True, text=True, encoding='utf-8').stdout

    def test_freeze_commit_tag_and_confirm_remote_without_changing_source(self):
        result = self.service.publish(self.project, self.spec)
        self.assertEqual(result['status'], 'pending_upload')
        self.assertEqual(result['manifest']['source_code_commit'], self.source)
        self.assertEqual(result['manifest']['validation_status'], 'not_accepted')
        self.assertEqual(self.git('rev-parse', 'HEAD').strip(), self.source)
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual(self.git('rev-parse', result['tag'] + '^{}').strip(), result['commit'])
        doc = self.service.document(self.project, self.spec, result['version'], 'spec.md')
        self.assertEqual(doc['content'], '# Spec AC-001 approved')
        repeated = self.service.publish(self.project, self.spec)
        self.assertEqual(repeated['version'], result['version'])
        synced = self.service.sync(self.project, self.spec, result['version'])
        self.assertEqual(synced['status'], 'remote_confirmed')
        self.assertEqual(self.service.list(self.project, self.spec)[0]['commit'], result['commit'])
        self.assertEqual(self.service.sync(self.project, self.spec, result['version'])['commit'], result['commit'])
        with self.assertRaises(ValueError):
            self.service.document(self.project, self.spec, result['version'], '../workbench.sqlite')

    def test_dirty_source_refused_without_archival_modification(self):
        (self.repo / 'private.txt').write_text('private')
        with self.assertRaises(ValueError):
            self.service.publish(self.project, self.spec)
        self.assertEqual(self.service.list(self.project, self.spec), [])

    def test_two_versions_keep_distinct_artifacts_and_index_links(self):
        first = self.service.publish(self.project, self.spec)
        run = self.store.start_run(self.project, self.spec, mode='runtime')
        changes = self.store.root / 'runs' / run['id'] / '.docloop/changes' / run['id']
        changes.mkdir(parents=True)
        (changes / 'tasks.md').write_text('TASK-001 新版本计划', encoding='utf-8')
        self.store.finish_run(self.project, run['id'], {'status': 'blocked'})
        second = self.service.publish(self.project, self.spec)
        self.assertNotEqual(first['version'], second['version'])
        self.assertEqual(first['version'], second['manifest']['previous_version'])
        index = self.service.document(self.project, self.spec, second['version'], 'version-index')['content']
        self.assertIn(first['version'], index)
        self.assertIn(second['version'], index)
        previous_manifest = self.git('show', second['commit'] + ':deliverables/' + first['version'] + '/manifest.json')
        self.assertEqual(first['version'], json.loads(previous_manifest)['version'])
        file = next(item for item in second['manifest']['files'] if item['path'].endswith('-tasks.md'))
        self.assertIn('TASK-001', self.service.document(self.project, self.spec, second['version'], file['path'])['content'])
        self.assertFalse((self.repo / 'deliverables').exists())

    def test_missing_remote_retry_preserves_original_commit(self):
        result = self.service.publish(self.project, self.spec)
        offline = self.root / 'offline.git'
        self.remote.rename(offline)
        try:
            failed = self.service.sync(self.project, self.spec, result['version'])
            self.assertEqual(failed['status'], 'upload_failed')
            self.assertNotIn(str(self.root), failed.get('error', ''))
        finally:
            offline.rename(self.remote)
        retried = self.service.sync(self.project, self.spec, result['version'])
        self.assertEqual(retried['status'], 'remote_confirmed')
        self.assertEqual(retried['commit'], result['commit'])


    def test_commit_before_ledger_crash_reconciles_original_commit(self):
        import docloop.publications as module
        save = module._save
        def crash(path, value):
            if value.get('status') == 'local_committed':
                raise OSError('simulated crash')
            return save(path, value)
        with patch.object(module, '_save', side_effect=crash):
            with self.assertRaises(OSError):
                self.service.publish(self.project, self.spec)
        record = self.service.list(self.project, self.spec)[0]
        staging = self.store.root / '.publication-staging' / record['version']
        committed = subprocess.run(['git', '-C', str(staging), 'rev-parse', 'HEAD'], check=True,
                                   capture_output=True, text=True).stdout.strip()
        recovered = self.service.publish(self.project, self.spec)
        self.assertEqual(recovered['commit'], committed)
        self.assertEqual(recovered['status'], 'pending_upload')

    def test_snapshot_before_ledger_crash_can_retry(self):
        import docloop.publications as module
        save = module._save
        def crash(path, value):
            if value.get('status') == 'frozen':
                raise OSError('simulated crash before ledger')
            return save(path, value)
        with patch.object(module, '_save', side_effect=crash):
            with self.assertRaises(OSError):
                self.service.publish(self.project, self.spec)
        result = self.service.publish(self.project, self.spec)
        self.assertEqual(result['status'], 'pending_upload')
        self.assertEqual(len(self.service.list(self.project, self.spec)), 1)

    def test_crlf_bytes_and_approved_hash_are_preserved(self):
        from hashlib import sha256
        content = '# Spec\r\nAC-001: original bytes\r\n'
        spec = self.store.create_spec(self.project, 'CRLF', content, 'sandbox', [], [])
        self.store.approve_spec(self.project, spec['id'], spec['sha256'], 1, 'tester')
        result = self.service.publish(self.project, spec['id'])
        expected = content.encode('utf-8')
        entry = next(item for item in result['manifest']['files'] if item['path'] == 'spec.md')
        self.assertEqual(entry['sha256'], sha256(expected).hexdigest())
        raw = subprocess.run(['git', '-C', str(self.repo), 'show',
            result['commit'] + ':deliverables/' + result['version'] + '/spec.md'],
            capture_output=True, check=True).stdout
        self.assertEqual(raw, expected)
        document = self.service.document(self.project, spec['id'], result['version'], 'spec.md')
        self.assertEqual(document['content'], content)
        self.assertEqual(document['sha256'], spec['sha256'])
        index = self.service.document(self.project, spec['id'], result['version'], 'version-index')
        self.assertIn(result['version'], index['content'])

    def test_repository_reregistration_rejects_old_publication_before_fetch(self):
        result = self.service.publish(self.project, self.spec)
        other = self.root / 'other'
        other.mkdir()
        for args in [('init',), ('-c', 'user.name=fixture', '-c', 'user.email=f@local', 'commit', '--allow-empty', '-m', 'other')]:
            subprocess.run(['git', '-C', str(other), *args], check=True, capture_output=True)
        ExecutionPreparation(self.store).register(self.project, str(other))
        with self.assertRaises(ValueError):
            self.service.sync(self.project, self.spec, result['version'])
        with self.assertRaises(ValueError):
            self.service.document(self.project, self.spec, result['version'], 'spec.md')
        refs = subprocess.run(['git', '-C', str(other), 'for-each-ref', 'refs/heads/docloop-deliveries'],
                              check=True, capture_output=True).stdout
        self.assertEqual(refs, b'')

    def test_remote_reconfiguration_rejects_old_publication(self):
        result = self.service.publish(self.project, self.spec)
        other_remote = self.root / 'other.git'
        subprocess.run(['git', 'init', '--bare', str(other_remote)], check=True, capture_output=True)
        self.git('remote', 'set-url', 'origin', str(other_remote))
        with self.assertRaises(ValueError):
            self.service.sync(self.project, self.spec, result['version'])
        refs = subprocess.run(['git', '-C', str(other_remote), 'show-ref'], capture_output=True).stdout
        self.assertEqual(refs, b'')

    def test_record_replace_retries_transient_windows_reader(self):
        import docloop.publications as module
        original = module.os.replace
        attempts = []
        def replace(source, target):
            attempts.append(target)
            if len(attempts) == 1:
                raise PermissionError('reader holds Windows file')
            return original(source, target)
        path = self.root / 'record.json'
        with patch.object(module.os, 'replace', side_effect=replace):
            module._save(path, {'status': 'frozen'})
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'status': 'frozen'})

    def test_run_documents_publish_under_long_windows_data_root(self):
        self.store.close()
        data_root = self.root / ('browser-fixture-' + 'x' * 20) / 'data'
        self.assertGreater(len(str(data_root)), 65)
        self.store = WorkbenchStore.sandbox(data_root)
        project = self.store.create_project('long path')['id']
        spec = self.store.create_spec(project, 'task', '# Spec AC-001 test', 'sandbox', [], [])
        self.store.approve_spec(project, spec['id'], spec['sha256'], 1, 'tester')
        ExecutionPreparation(self.store).register(project, str(self.repo))
        run = self.store.start_run(project, spec['id'])
        origin = self.store.root / 'runs' / run['id'] / '.docloop' / 'changes' / run['id'] / 'tasks.md'
        origin.parent.mkdir(parents=True)
        origin.write_bytes(b'# TASK-001\r\n')
        service = PublicationService(self.store)
        publication = service.publish(project, spec['id'])
        entry = next(item for item in publication['manifest']['files'] if item['path'] != 'spec.md')
        self.assertEqual(entry['source_path'], origin.relative_to(data_root).as_posix())
        self.assertLess(len(entry['path']), 64)
        self.assertEqual(service.document(project, spec['id'], publication['version'], entry['path'])['content'], '# TASK-001\r\n')

    def test_crlf_commit_crash_reconciles_with_text_attributes(self):
        import docloop.publications as module
        (self.repo / '.gitattributes').write_text('*.md text eol=lf\n', encoding='utf-8')
        self.git('add', '.gitattributes')
        self.git('commit', '-m', 'text attributes')
        spec = self.store.create_spec(self.project, 'CRLF', '# Spec\r\nAC-001: bytes\r\n', 'sandbox', [], [])
        self.store.approve_spec(self.project, spec['id'], spec['sha256'], 1, 'tester')
        save = module._save
        def crash(path, value):
            if value.get('status') == 'local_committed':
                raise OSError('crash after CRLF commit')
            return save(path, value)
        with patch.object(module, '_save', side_effect=crash):
            with self.assertRaises(OSError):
                self.service.publish(self.project, spec['id'])
        record = self.service.list(self.project, spec['id'])[0]
        stage = self.store.root / '.publication-staging' / record['version']
        committed = subprocess.run(['git', '-C', str(stage), 'rev-parse', 'HEAD'],
                                   check=True, capture_output=True, text=True).stdout.strip()
        result = self.service.publish(self.project, spec['id'])
        self.assertEqual(result['commit'], committed)
        self.assertEqual(result['status'], 'pending_upload')
