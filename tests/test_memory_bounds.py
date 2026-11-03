"""使用临时资料库测量大资料历史的 Python 分配峰值。"""
import gc
import tempfile
import tracemalloc
import unittest
from contextlib import closing
from pathlib import Path
from docloop.workbench_store import WorkbenchStore


class MemoryBoundsTests(unittest.TestCase):
    def test_document_metadata_and_import_do_not_load_history_bodies(self):
        with tempfile.TemporaryDirectory() as folder, closing(WorkbenchStore.sandbox(Path(folder))) as store:
            pid = store.create_project('memory')['id']
            for index in range(24):
                store.import_document(pid, 'large.txt', (str(index) + 'x' * 500000).encode())
            gc.collect()
            tracemalloc.start()
            try:
                docs = store.documents(pid)
                store.import_document(pid, 'large.txt', b'new version')
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            self.assertEqual(len(docs), 24)
            self.assertEqual(docs[0]['version'], 24)
            self.assertLess(peak, 4 * 1024 * 1024, f'history allocated {peak} bytes')

    def test_search_keeps_only_top_hits_in_memory(self):
        with tempfile.TemporaryDirectory() as folder, closing(WorkbenchStore.sandbox(Path(folder))) as store:
            pid = store.create_project('search')['id']
            for index in range(20):
                store.import_document(pid, f'{index}.txt', b'needle line\n' * 20000)
            gc.collect()
            tracemalloc.start()
            try:
                hits = store.search(pid, 'needle')
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            self.assertEqual(len(hits), 6)
            self.assertEqual(hits[0]['score'], 16)
            self.assertLess(peak, 8 * 1024 * 1024, f'search allocated {peak} bytes')
