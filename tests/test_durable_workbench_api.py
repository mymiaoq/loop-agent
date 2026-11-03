import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from docloop.workbench import create_app

ROOT = Path(__file__).resolve().parents[1]


class DurableApiTests(unittest.TestCase):
    def test_analysis_control_skill_labels_and_refresh_are_persistent(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(ROOT, Path(directory))
            with TestClient(app, base_url='http://127.0.0.1') as client:
                state = client.get('/api/state').json()
                pid = state['project_id']
                headers = {'X-DocLoop-Token': state['csrf_token']}
                root = '/api/projects/' + pid
                body = {'title': '后台任务', 'requirement': '导出文件', 'mode': 'sandbox', 'request_id': 'same'}
                response = client.post(root + '/analysis-tasks', json=body, headers=headers)
                self.assertEqual(200, response.status_code, response.text)
                sid = response.json()['id']
                service = app.state.service
                run = service.store.task_runs(pid, sid)[0]
                service.runtime().wait(pid, run['id'], 5)
                self.assertEqual(sid, client.post(root + '/analysis-tasks', json=body, headers=headers).json()['id'])
                self.assertEqual(1, len(client.get('/api/state').json()['runs']))
                sources = client.get('/api/state').json()['specs'][0]['skill_sources']
                self.assertTrue(all(item.get('display_name') and item.get('description') for item in sources))
                self.assertEqual([], client.get(root + '/specs/' + sid + '/publications').json()['publications'])
                skills = client.get('/api/skills').json()['skills']
                self.assertTrue(all(item.get('display_name') and item.get('description') for item in skills))
                self.assertEqual('需求规格整理', next(item for item in skills if item['name'] == 'spec-create')['display_name'])

    def test_cross_project_control_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(ROOT, Path(directory))
            with TestClient(app, base_url='http://127.0.0.1') as client:
                state = client.get('/api/state').json()
                headers = {'X-DocLoop-Token': state['csrf_token']}
                store = app.state.service.store
                pid = state['project_id']
                spec = store.create_spec(pid, '任务', 'AC-001 任务', 'sandbox', [], [])
                store.approve_spec(pid, spec['id'], spec['sha256'], 1, 'tester')
                run = store.start_run(pid, spec['id'])
                other = store.create_project('other')['id']
                for command in ('pause', 'resume', 'cancel'):
                    path = f'/api/projects/{other}/runtime-runs/{run["id"]}/{command}'
                    self.assertEqual(404, client.post(path, headers=headers, json={}).status_code)
