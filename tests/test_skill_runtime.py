import json
import shutil
import tempfile
import unittest
from pathlib import Path
import yaml

from docloop.governance import GateError
from docloop.project import inspect_project
from docloop.skill_runtime import SkillRegistry
from docloop.workflow import Workflow

ROOT = Path(__file__).resolve().parents[1]


class LocalSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        shutil.copytree(ROOT / '.docloop', cls.root / '.docloop',
                        ignore=shutil.ignore_patterns('changes', 'checkpoints', 'sessions', 'traces', 'recovery'))
        shutil.copy(ROOT / 'AGENTS.md', cls.root / 'AGENTS.md')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def registry(self):
        return SkillRegistry(self.root)

    def change_file(self, relative, suffix):
        path = self.root / relative
        original = path.read_bytes()
        self.addCleanup(path.write_bytes, original)
        path.write_bytes(original + suffix.encode('utf-8'))
        return path

    def test_next_load_reads_edited_project_local_skill(self):
        registry = self.registry()
        before = registry.load('superpowers:brainstorming')
        self.change_file('.docloop/superpowers/skills/brainstorming/SKILL.md', '\nLOCAL-BRAINSTORMING-MARKER\n')
        after = registry.load('superpowers:brainstorming')
        self.assertIn('LOCAL-BRAINSTORMING-MARKER', after['content'])
        self.assertNotEqual(before['sha256'], after['sha256'])
        self.assertEqual(after['path'], '.docloop/superpowers/skills/brainstorming/SKILL.md')
        report = inspect_project(self.root)['superpowers']
        self.assertTrue(report['installed'])
        self.assertFalse(report['upstream_matches'])
        self.assertIn('skills/brainstorming/SKILL.md', report['changes']['modified'])

    def test_custom_skill_is_read_from_docloop_directory(self):
        self.change_file('.docloop/skills/spec-create/SKILL.md', '\nLOCAL-SPEC-MARKER\n')
        skill = self.registry().load('docloop:spec-create')
        self.assertIn('LOCAL-SPEC-MARKER', skill['content'])
        self.assertEqual(skill['path'], '.docloop/skills/spec-create/SKILL.md')

    def test_no_fallback_when_local_skill_missing(self):
        with self.assertRaises(GateError):
            self.registry().load('docloop:brainstorming')
        for ref in ('superpowers:../brainstorming', 'global:brainstorming', 'superpowers:/brainstorming'):
            with self.subTest(ref=ref), self.assertRaises(GateError):
                self.registry().load(ref)

    def test_resources_resolve_in_local_tree_and_cannot_escape(self):
        resource = self.registry().read_resource('superpowers:using-superpowers', 'references/codex-tools.md')
        self.assertTrue(resource['path'].startswith('.docloop/superpowers/skills/using-superpowers/'))
        self.assertTrue(resource['content'].strip())
        with self.assertRaises(GateError):
            self.registry().read_resource('superpowers:brainstorming', '../../../../project.yaml')

    def test_agent_packet_consumes_local_contents_and_only_selected_rules(self):
        self.change_file('.docloop/superpowers/skills/brainstorming/SKILL.md', '\nLOCAL-PROMPT-MARKER\n')
        packet = self.registry().build_agent_input('spec', {'change_id': 'context-only',
            'rules': ['code-standard'], 'excluded_rules': ['api-standard'], 'skills': []})
        self.assertEqual(packet['role'], 'spec-agent')
        self.assertIn('LOCAL-PROMPT-MARKER', packet['messages'][0]['content'])
        self.assertEqual([x['ref'] for x in packet['skills']],
                         ['superpowers:using-superpowers', 'docloop:spec-create', 'docloop:document-parser', 'superpowers:brainstorming'])
        self.assertEqual([x['name'] for x in packet['rules']], ['code-standard'])
        self.assertFalse(packet['model_invoked'])

    def test_workflow_loads_local_files_before_pause_and_planning(self):
        self.change_file('.docloop/superpowers/skills/brainstorming/SKILL.md', '\nWORKFLOW-LOCAL-SPEC\n')
        self.change_file('.docloop/superpowers/skills/writing-plans/SKILL.md', '\nWORKFLOW-LOCAL-PLAN\n')
        with Workflow(self.root) as flow:
            result = flow.start('local-routing-1', 'AC-001: test local routing', mode='real')
            self.assertIn('__interrupt__', result)
            folder = flow.gov.path('local-routing-1') / 'agent-inputs'
            spec = json.loads(next(folder.glob('spec-*.json')).read_text(encoding='utf-8'))
            self.assertIn('WORKFLOW-LOCAL-SPEC', spec['messages'][0]['content'])
            result = flow.approve('local-routing-1', flow.gov.digest('local-routing-1'), 'test-user')
            self.assertEqual(result['status'], 'blocked')
            plan = json.loads(next(folder.glob('plan-*.json')).read_text(encoding='utf-8'))
            self.assertIn('WORKFLOW-LOCAL-PLAN', plan['messages'][0]['content'])
        events = [json.loads(line) for line in (self.root / '.docloop/traces/local-routing-1.jsonl').read_text(encoding='utf-8').splitlines()]
        loads = [event for event in events if event.get('event') == 'skill.loaded']
        self.assertTrue(any(event['ref'] == 'superpowers:brainstorming' for event in loads))
        self.assertTrue(all(event['path'].startswith('.docloop/') for event in loads))

    def test_excluded_rule_cannot_be_in_prompt(self):
        with self.assertRaises(GateError):
            self.registry().build_agent_input('spec', {'rules': ['api-standard'],
                'excluded_rules': ['api-standard'], 'skills': []})

    def test_strict_policy_is_enforced_when_loading(self):
        config_file = self.root / '.docloop/project.yaml'
        original = config_file.read_bytes()
        self.addCleanup(config_file.write_bytes, original)
        config = yaml.safe_load(original)
        config['superpowers']['integrity_policy'] = 'strict'
        config_file.write_text(yaml.safe_dump(config), encoding='utf-8')
        self.change_file('.docloop/superpowers/skills/brainstorming/SKILL.md', '\nSTRICT-MODIFICATION\n')
        with self.assertRaises(GateError):
            self.registry().load('superpowers:brainstorming')

    def test_invalid_route_is_rejected_by_doctor_and_saved_as_blocker(self):
        config_file = self.root / '.docloop/project.yaml'
        original = config_file.read_bytes()
        self.addCleanup(config_file.write_bytes, original)
        config = yaml.safe_load(original)
        config['skill_runtime']['stages']['plan'] = [123]
        config_file.write_text(yaml.safe_dump(config), encoding='utf-8')
        with self.assertRaises(GateError):
            inspect_project(self.root)
        with Workflow(self.root) as flow:
            result = flow.start('bad-route-1', 'AC-001: explicit blocker', mode='real')
        self.assertEqual(result['status'], 'blocked')
        self.assertTrue((self.root / '.docloop/recovery/bad-route-1.json').exists())
