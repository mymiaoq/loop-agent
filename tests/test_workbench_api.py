import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from docloop.workbench import create_app

ROOT = Path(__file__).resolve().parents[1]


class WorkbenchApiTests(unittest.TestCase):
    def test_model_options_and_persistent_selection_are_restricted(self):
        selected = self.client.post('/api/settings/model/select', headers=self.headers,
            json={'model': 'deepseek-v4.1-flash'})
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(len(selected.json()['options']), 2)
        self.assertFalse(selected.json()['configured'])
        self.assertEqual(self.client.post('/api/settings/model/select', headers=self.headers,
            json={'model': 'other-model'}).status_code, 400)
        from docloop.model_gateway import ModelGateway
        restored = ModelGateway(settings_path=Path(self.tmp.name) / '.settings/model-settings.json')
        self.assertEqual(restored.public_config()['model'], 'deepseek-v4.1-flash')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = create_app(ROOT, Path(self.tmp.name))
        self.client = TestClient(self.app, base_url='http://127.0.0.1')
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.state = self.client.get('/api/state').json()
        self.token = self.state['csrf_token']
        self.headers = {'X-DocLoop-Token': self.token}
        self.pid = self.state['project_id']

    def test_browser_contract_full_approval_and_reopen(self):
        base = '/api/projects/' + self.pid
        imported = self.client.post(base + '/documents', headers=self.headers,
            json={'name': '审批规则.md', 'content': '必须保留审批原始版本和来源。'})
        self.assertEqual(imported.status_code, 200, imported.text)
        generated = self.client.post(base + '/specs', headers=self.headers,
            json={'title': '审批', 'requirement': '实现审批并保留来源', 'mode': 'sandbox'})
        self.assertEqual(generated.status_code, 200, generated.text)
        spec = generated.json()
        path = base + '/specs/' + spec['id']
        blocked = self.client.post(path + '/runs', headers=self.headers, json={})
        self.assertEqual(blocked.status_code, 409)
        approved = self.client.post(path + '/approve', headers=self.headers,
            json={'sha256': spec['sha256'], 'revision': spec['revision'], 'approver': '测试用户'})
        self.assertEqual(approved.status_code, 200, approved.text)
        run = self.client.post(path + '/runs', headers=self.headers, json={'scenario': 'success'})
        self.assertEqual(run.status_code, 200, run.text)
        self.assertEqual(run.json()['status'], 'accepted')
        self.assertFalse(run.json()['result']['real_business_acceptance'])
        execution = self.client.get(path + '/execution')
        self.assertEqual(execution.status_code, 200)
        self.assertTrue(any(record['type'] == 'verification' for record in execution.json()['records']))
        self.assertEqual(execution.json()['artifacts'][0]['sha256'], spec['sha256'])
        self.assertEqual(self.client.get('/api/state').json()['task_summaries'][spec['id']]['status'], 'accepted')

    def test_cross_origin_and_missing_token_rejected(self):
        path = '/api/projects'
        self.assertEqual(self.client.post(path, json={'name': 'bad'}).status_code, 403)
        self.assertEqual(self.client.post(path, headers={**self.headers, 'Origin': 'https://evil.invalid'},
            json={'name': 'bad'}).status_code, 403)
        self.assertEqual(self.client.get('/api/state', headers={'Host': 'evil.invalid'}).status_code, 403)

    def test_no_unconfigured_real_fallback_and_skills_are_local(self):
        response = self.client.post('/api/projects/' + self.pid + '/specs', headers=self.headers,
            json={'title': '真实', 'requirement': '测试真实请求', 'mode': 'real'})
        self.assertEqual(response.status_code, 502)
        skill = self.client.get('/api/skills/superpowers/brainstorming').json()
        self.assertEqual(skill['path'], '.docloop/superpowers/skills/brainstorming/SKILL.md')
        self.assertNotIn('api_key', self.client.get('/api/state').json()['environment']['model'])

    def test_revision_conflict_and_project_boundaries(self):
        base = '/api/projects/' + self.pid
        spec = self.client.post(base + '/specs', headers=self.headers,
            json={'title': '草稿', 'requirement': '版本检查', 'mode': 'sandbox'}).json()
        other = self.client.post('/api/projects', headers=self.headers, json={'name': '另一个项目'}).json()['id']
        path = base + '/specs/' + spec['id']
        self.assertEqual(self.client.put(path, headers=self.headers,
            json={'content': 'AC-001: edit', 'revision': 999}).status_code, 409)
        self.assertEqual(self.client.put('/api/projects/' + other + '/specs/' + spec['id'], headers=self.headers,
            json={'content': 'AC-001: cross-project', 'revision': 1}).status_code, 404)
        self.assertEqual(self.client.get('/api/projects/' + other + '/specs/' + spec['id'] +
            '/deliverables/bundle').status_code, 404)

    def test_health_identity_and_stop_require_local_session(self):
        health = self.client.get('/api/health').json()
        self.assertEqual(health['application'], 'docloop-workbench')
        self.assertEqual(Path(health['data_root']), Path(self.tmp.name).resolve())
        stopped = []
        self.app.state.stop_callback = lambda: stopped.append(True)
        self.assertEqual(self.client.post('/api/shutdown').status_code, 403)
        response = self.client.post('/api/shutdown', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(stopped, [True])
