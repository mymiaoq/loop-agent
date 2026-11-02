"""真实浏览器验收；所有业务数据位于系统临时沙箱。"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]


class WorkbenchBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='docloop-browser-')
        cls.data = Path(cls.temp.name)
        cls.evidence = Path(os.environ.get('DOCLOOP_BROWSER_EVIDENCE', str(cls.data / 'evidence')))
        cls.evidence.mkdir(parents=True, exist_ok=True)
        cls.log_path = cls.data / 'server.log'
        cls.log = cls.log_path.open('w', encoding='utf-8')
        cls.process = subprocess.Popen([sys.executable, '-m', 'docloop.workbench', '--root', str(ROOT),
            '--data-root', str(cls.data / 'data'), '--port', '0'], stdout=cls.log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        for _ in range(150):
            content = cls.log_path.read_text(encoding='utf-8', errors='replace')
            match = re.search(r'http://127\.0\.0\.1:\d+', content)
            if match:
                cls.url = match.group()
                break
            if cls.process.poll() is not None:
                raise RuntimeError(content)
            time.sleep(0.1)
        else:
            raise RuntimeError('Workbench did not start')
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(channel=os.getenv('DOCLOOP_BROWSER_CHANNEL', 'msedge'), headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        if cls.process.poll() is None:
            cls.process.terminate()
        cls.process.wait(timeout=15)
        cls.log.close()
        (cls.evidence / 'server.log').write_text(cls.log_path.read_text(encoding='utf-8', errors='replace'), encoding='utf-8')
        cls.temp.cleanup()

    def test_full_browser_flow_layout_and_refresh(self):
        page = self.browser.new_page(viewport={'width': 1366, 'height': 1000})
        self.addCleanup(page.close)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        page.goto(self.url)
        expect(page.locator('#generate')).to_be_enabled()
        original_project = page.locator('#project').input_value()
        page.locator('#generate').click()
        expect(page.locator('#notice')).to_contain_text('请填写')
        page.locator('[data-page="documents"]').click()
        page.locator('#paste-name').fill('审批来源-长名称-用于验证行号和版本.md')
        page.locator('#paste-content').fill('项目资料导入后必须人工审批。\n审批需要保留Spec版本、来源和指纹。')
        page.locator('#add-text').click()
        expect(page.locator('#document-list')).to_contain_text('审批来源')
        page.locator('[data-page="workspace"]').click()
        page.locator('#spec-title').fill('资料导入与审批')
        page.locator('#requirement').fill('导入项目资料并审批Spec，保留来源与版本。')
        page.locator('#generate').click()
        expect(page.locator('#spec-detail')).to_be_visible()
        expect(page.locator('#references')).to_contain_text('审批来源')
        original = page.locator('#spec-content').input_value()
        edited = original + '\nAC-003：验收工作台刷新恢复。\n'
        page.locator('#spec-content').fill(edited)
        page.evaluate('refresh(state.project_id)')
        self.assertEqual(page.locator('#spec-content').input_value(), edited,
                         'Background refresh silently discarded dirty Spec')
        held = []
        page.route('**/api/projects/*/specs/*', lambda route: held.append(route)
                   if route.request.method == 'PUT' else route.continue_())
        page.locator('#save-spec').click()
        for _ in range(30):
            if held:
                break
            page.wait_for_timeout(50)
        self.assertTrue(held)
        self.assertTrue(page.locator('#spec-content').evaluate('(node)=>node.readOnly'),
                        'Editor accepts unsaved edits while save is in flight')
        held[0].continue_()
        expect(page.locator('#spec-revision')).to_contain_text('2')
        page.unroute('**/api/projects/*/specs/*')
        page.locator('#approve-spec').click()
        expect(page.locator('#modal')).to_be_visible()
        page.locator('#approver').fill('浏览器沙箱测试')
        page.get_by_role('button', name='确认批准此指纹').click()
        expect(page.locator('#spec-status')).to_have_text('已批准')
        page.locator('#run-spec').click()
        expect(page.locator('#run-spec')).to_be_enabled(timeout=30000)
        page.locator('[data-page="runs"]').click()
        expect(page.locator('#run-list')).to_contain_text('accepted')
        expect(page.locator('#run-list')).to_contain_text('非真实业务验收')
        page.reload()
        expect(page.locator('#spec-status')).to_have_text('已批准')
        expect(page.locator('#spec-content')).to_have_value(edited)
        page.locator('[data-page="documents"]').click()
        page.locator('#paste-name').fill('审批来源-长名称-用于验证行号和版本.md')
        page.locator('#paste-content').fill('新版资料：不同于旧版的业务内容。')
        page.locator('#add-text').click()
        expect(page.locator('#document-list')).to_contain_text('版本 2')
        page.locator('[data-page="workspace"]').click()
        expect(page.locator('#references')).to_contain_text('v1')
        expect(page.locator('#references')).to_contain_text('历史引用快照')
        for width in (1366, 1920, 390):
            page.set_viewport_size({'width': width, 'height': 1000})
            self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'),
                            f'Page overflow at width {width}')
            page.screenshot(path=str(self.evidence / f'workbench-{width}.png'), full_page=True)
        page.locator('[data-page="skills"]').click()
        expect(page.locator('#skill-list')).to_contain_text('brainstorming')
        page.locator('#skill-list .row').filter(has_text='superpowers/skills/brainstorming/').get_by_role('button').click()
        expect(page.locator('#modal-body')).to_contain_text('.docloop/superpowers/skills/brainstorming/SKILL.md')
        page.keyboard.press('Escape')
        expect(page.locator('#modal')).not_to_be_visible()
        page.locator('[data-page="settings"]').click()
        expect(page.locator('#environment-info')).to_contain_text('sandbox-sqlite')
        page.once('dialog', lambda dialog: dialog.accept('浏览器隔离项目'))
        page.locator('#new-project').click()
        page.locator('[data-page="workspace"]').click()
        expect(page.locator('#spec-empty')).to_be_visible()
        new_project = page.locator('#project').input_value()
        self.assertNotEqual(new_project, original_project)
        page.reload()
        expect(page.locator('#project')).to_have_value(new_project)
        page.locator('#project').select_option(original_project)
        expect(page.locator('#spec-status')).to_have_text('已批准')
        self.assertEqual(errors, [])
        from docloop.workbench import find_instance, stop_existing
        port = int(self.url.rsplit(':', 1)[1])
        self.assertEqual(find_instance(ROOT, self.data / 'data', port, 'sandbox'), self.url)
        self.assertIsNone(find_instance(ROOT, self.data / 'data', port, 'oracle'))
        self.assertTrue(stop_existing(ROOT, self.data / 'data', port)['ok'])
        self.process.wait(timeout=15)
        (self.evidence / 'browser-result.json').write_text(json.dumps({
            'status': 'passed', 'viewport_widths': [1366, 1920, 390], 'console_errors': errors,
            'flows': ['document import', 'local Skill-backed sandbox draft', 'dirty refresh',
                      'save in flight lock', 'Hash approval', 'isolated LangGraph run', 'reload restore', 'local Skill preview'],
            'oracle_live': 'not_run', 'provider_inference': 'not_run'}, ensure_ascii=False, indent=2), encoding='utf-8')
