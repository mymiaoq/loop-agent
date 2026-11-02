import json
import shutil
import tempfile
import unittest
from pathlib import Path

from docloop.governance import GateError
from docloop.project import inspect_project
from docloop.superpowers import inspect_superpowers

ROOT = Path(__file__).resolve().parents[1]


class SuperpowersTests(unittest.TestCase):
    def test_vendored_source_matches_pin_and_all_file_hashes(self):
        report = inspect_project(ROOT)['superpowers']
        self.assertTrue(report['installed'])
        self.assertTrue(report['integrity_verified'])
        self.assertEqual(report['skill_count'], 15)
        self.assertFalse(report['runtime_loaded'])

    def test_modified_upstream_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / '.docloop/superpowers', root / '.docloop/superpowers')
            shutil.copy(ROOT / '.docloop/superpowers.lock.json', root / '.docloop/superpowers.lock.json')
            skill = root / '.docloop/superpowers/skills/brainstorming/SKILL.md'
            skill.write_text('modified', encoding='utf-8')
            with self.assertRaises(GateError):
                inspect_superpowers(root, {'commit': '2ce8aa15d05bd57213e6f746f953aafb7ded7a8b',
                    'repository': 'https://github.com/obra/superpowers.git', 'enabled': False,
                    'install_path': '.docloop/superpowers', 'manifest_path': '.docloop/superpowers.lock.json'})

    def test_pin_mismatch_and_escaping_install_path_rejected(self):
        config = {'commit': '0' * 40, 'repository': 'https://github.com/obra/superpowers.git',
                  'enabled': False, 'install_path': '.docloop/superpowers',
                  'manifest_path': '.docloop/superpowers.lock.json'}
        with self.assertRaises(GateError):
            inspect_superpowers(ROOT, config)
        config['install_path'] = '../outside'
        with self.assertRaises(GateError):
            inspect_superpowers(ROOT, config)
