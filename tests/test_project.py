import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from docloop.project import REQUIRED_SKILLS, inspect_project, read_yaml, route_skills
from docloop.governance import GateError

ROOT = Path(__file__).resolve().parents[1]


class ProjectTests(unittest.TestCase):
    def test_profile_loads_only_applicable_rules_and_validates_contracts(self):
        report = inspect_project(ROOT)
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(len(report['agents']), 5)
        # document-parser 同时出现在平台与领域列表，按名字去重后是15个。
        self.assertEqual(len(report['skills']), 15)
        self.assertNotIn('ui-standard', report['active_rules'])
        self.assertNotIn('api-standard', report['active_rules'])

    def test_all_required_docloop_skills_are_routed_and_enterprise_is_gated(self):
        config = read_yaml(ROOT / '.docloop/project.yaml')
        refs = []
        for selected in config['skill_runtime']['stages'].values():
            refs.extend(ref for ref in selected if not ref.startswith('superpowers:'))
        for selected in config['routing'].values():
            refs.extend(ref for ref in selected if not ref.startswith('superpowers:'))
        names = {ref.split(':', 1)[1] if ':' in ref else ref for ref in refs}
        self.assertEqual(names, REQUIRED_SKILLS)
        self.assertTrue(route_skills(ROOT, ['workflow']))
        with self.assertRaises(GateError):
            route_skills(ROOT, ['ui'])

    def test_cli_demo_runs_in_separate_process_and_invalid_hash_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            def cli(*args):
                return subprocess.run([sys.executable, '-m', 'docloop', '--root', tmp, *args],
                                      capture_output=True, text=True, encoding='utf-8', timeout=60)
            start = cli('demo', '--change-id', 'cli-1')
            self.assertEqual(start.returncode, 0, start.stderr)
            data = json.loads(start.stdout)
            self.assertEqual(data['status'], 'draft')
            bad = cli('approve', 'cli-1', '--hash', 'wrong', '--by', 'tester')
            self.assertNotEqual(bad.returncode, 0)
            done = cli('approve', 'cli-1', '--hash', data['spec_sha256'], '--by', 'tester')
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(json.loads(done.stdout)['status'], 'accepted')

    def test_doctor_rejects_missing_skill(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            shutil.copytree(ROOT / '.docloop', target / '.docloop',
                            ignore=shutil.ignore_patterns('changes', 'checkpoints', 'sessions', 'traces', 'recovery'))
            shutil.copy(ROOT / 'AGENTS.md', target / 'AGENTS.md')
            (target / '.docloop/skills/test-runner/SKILL.md').unlink()
            with self.assertRaises(GateError):
                inspect_project(target)
