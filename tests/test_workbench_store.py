import tempfile
import unittest
from pathlib import Path
from docloop.workbench_store import WorkbenchStore, Conflict, NotFound


class WorkbenchStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = WorkbenchStore.sandbox(self.root)
        self.addCleanup(self.store.close)
        self.project = self.store.create_project('项目甲')
        self.other = self.store.create_project('项目乙')

    def test_import_dedup_version_and_project_isolation(self):
        pid = self.project['id']
        first = self.store.import_document(pid, '需求.md', '审批必须保留原始版本'.encode())
        repeated = self.store.import_document(pid, '需求.md', '审批必须保留原始版本'.encode())
        self.assertEqual(first['document']['id'], repeated['document']['id'])
        self.assertTrue(repeated['deduplicated'])
        second = self.store.import_document(pid, '需求.md', '新版本：支持资料检索'.encode())
        self.assertEqual(second['document']['version'], 2)
        self.assertEqual(self.store.search(self.other['id'], '审批'), [])
        self.assertEqual(self.store.search(pid, '审批'), [])
        self.assertTrue(self.store.search(pid, '资料检索'))
        self.store.deactivate_document(pid, second['document']['id'])
        self.assertEqual(self.store.search(pid, '资料检索'), [])

    def test_document_input_and_owner_are_checked(self):
        for name, raw in [('bad.pdf', b'PDF'), ('../bad.md', b'x'), ('a.md', b'\xff'), ('a.md', b'')]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.store.import_document(self.project['id'], name, raw)
        doc = self.store.import_document(self.project['id'], 'a.txt', b'text')['document']
        with self.assertRaises(NotFound):
            self.store.deactivate_document(self.other['id'], doc['id'])

    def test_approval_is_atomic_hash_bound_and_immutable(self):
        pid = self.project['id']
        spec = self.store.create_spec(pid, '方案', 'AC-001: check', 'sandbox', [], [])
        with self.assertRaises(Conflict):
            self.store.approve_spec(pid, spec['id'], 'wrong', spec['revision'], 'tester')
        edited = self.store.save_spec(pid, spec['id'], 'AC-001: edited', spec['revision'])
        with self.assertRaises(Conflict):
            self.store.save_spec(pid, spec['id'], 'AC-001: stale', spec['revision'])
        approved = self.store.approve_spec(pid, spec['id'], edited['sha256'], edited['revision'], 'tester')
        self.assertEqual(approved['status'], 'approved')
        self.assertEqual(self.store.approved_bytes(pid, spec['id']), b'AC-001: edited')
        with self.assertRaises(Conflict):
            self.store.save_spec(pid, spec['id'], 'AC-001: overwrite', approved['revision'])
        with self.assertRaises(NotFound):
            self.store.spec(self.other['id'], spec['id'])

    def test_reopen_preserves_docs_spec_and_approval(self):
        pid = self.project['id']
        doc = self.store.import_document(pid, 'test.txt', b'line 1\nimportant source\nline 3')['document']
        hits = self.store.search(pid, 'important')
        spec = self.store.create_spec(pid, 'persistent', 'AC-001: restore', 'sandbox', hits, [])
        self.store.approve_spec(pid, spec['id'], spec['sha256'], spec['revision'], 'tester')
        reopened = WorkbenchStore.sandbox(self.root)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.spec(pid, spec['id'])['references'][0]['document_id'], doc['id'])
        self.assertEqual(reopened.approved_bytes(pid, spec['id']), b'AC-001: restore')

    def test_oracle_schema_uses_clob_blob_and_no_sqlite_fallback(self):
        ddl = self.store.oracle_ddl()
        self.assertIn('CLOB', ddl)
        self.assertIn('BLOB', ddl)
        self.assertIn('dl_spec', ddl.lower())
        with self.assertRaises(ValueError):
            WorkbenchStore.oracle(self.root, user=None, password=None, dsn=None)

    def test_restart_marks_interrupted_run_blocked_without_rerunning(self):
        pid = self.project['id']
        spec = self.store.create_spec(pid, '恢复', 'AC-001: restart', 'sandbox', [], [])
        self.store.approve_spec(pid, spec['id'], spec['sha256'], 1, 'tester')
        run = self.store.start_run(pid, spec['id'])
        self.store.recover_interrupted_runs()
        restored = next(item for item in self.store.history(pid) if item['id'] == run['id'])
        self.assertEqual(restored['status'], 'blocked')
        self.assertTrue(restored['result']['interrupted'])

    def test_concurrent_approval_only_one_revision_wins(self):
        from concurrent.futures import ThreadPoolExecutor
        pid = self.project['id']
        spec = self.store.create_spec(pid, '并发', 'AC-001: concurrency', 'sandbox', [], [])
        def approve(index):
            try:
                self.store.approve_spec(pid, spec['id'], spec['sha256'], 1, str(index))
                return 'approved'
            except Conflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(approve, range(4)))
        self.assertEqual(results.count('approved'), 1)
        self.assertEqual(results.count('conflict'), 3)
