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
            env={**os.environ, 'CODEX_APP_RUNTIME_CLI_PATH': sys.executable},
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
        def controlled_generation(route):
            body = route.request.post_data_json
            if route.request.method == 'POST' and body.get('mode') == 'real':
                route.fulfill(status=400, json={'detail': 'Browser fixture does not invoke a real provider'})
            else:
                route.continue_()
        page.route('**/api/projects/*/specs', controlled_generation)
        expect(page.locator('#generate')).to_be_enabled()
        expect(page.locator('#task-list')).to_be_visible()
        session = page.request.get(self.url + '/api/state').json()
        configured = page.request.post(self.url + '/api/settings/model',
            headers={'X-DocLoop-Token': session['csrf_token']}, data={'model': 'gpt-6.1-sol'})
        self.assertEqual(configured.status, 200)
        page.locator('#active-model').select_option('deepseek-v4.1-flash')
        expect(page.locator('#active-model')).to_be_enabled()
        page.reload()
        expect(page.locator('#active-model')).to_have_value('deepseek-v4.1-flash')
        page.locator('[data-page="settings"]').click()
        page.locator('#api-key').fill('browser-test-private-key')
        page.get_by_role('button', name='保存模型配置').click()
        expect(page.locator('#notice')).to_contain_text('模型配置已保存')
        page.reload()
        expect(page.locator('#active-model')).to_have_value('deepseek-v4.1-flash')
        self.assertTrue(page.evaluate('window.docloopState.environment.model.has_api_key'))
        self.assertEqual(page.locator('#api-key').input_value(), '')
        page.locator('#active-model').select_option('gpt-6.1-sol')
        expect(page.locator('#active-model')).to_be_enabled()
        page.locator('#generation-mode').select_option('sandbox')
        def task_drawer():
            toggle = page.locator('#drawer-toggle')
            if toggle.is_visible() and toggle.get_attribute('aria-expanded') != 'true':
                toggle.click()
        original_project = page.locator('#project').input_value()
        page.locator('#generate').click()
        expect(page.locator('#notice')).to_contain_text('请填写')
        page.locator('[data-page="documents"]').click()
        page.locator('#paste-name').fill('审批来源-长名称-用于验证行号和版本.md')
        page.locator('#paste-content').fill('项目资料导入后必须人工审批。\n审批需要保留Spec版本、来源和指纹。')
        page.locator('#add-text').click()
        expect(page.locator('#document-list')).to_contain_text('审批来源')
        page.locator('[data-page="workspace"]').click()
        self.assertEqual(page.locator('#spec-title').count(), 0)
        expect(page.locator('#active-model option')).to_have_count(2)
        page.locator('#requirement').fill('资料导入与审批\n导入项目资料并审批Spec，保留来源与版本。')
        page.locator('#generate').click()
        expect(page.locator('#spec-detail')).to_be_visible()
        expect(page.locator('#references')).to_contain_text('审批来源')
        original = page.locator('#spec-content').input_value()
        edited = original + '\nAC-003：验收工作台刷新恢复。\n<script>window.artifactInjected=true</script>\n'
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
        page.locator('[data-view="spec"]').click()
        expect(page.locator('#spec-status')).to_have_text('已批准')
        expect(page.locator('#spec-content')).to_have_value(edited)
        page.locator('[data-page="documents"]').click()
        page.locator('#paste-name').fill('审批来源-长名称-用于验证行号和版本.md')
        page.locator('#paste-content').fill('新版资料：不同于旧版的业务内容。')
        page.locator('#add-text').click()
        expect(page.locator('#document-list')).to_contain_text('版本 2')
        page.locator('[data-page="workspace"]').click()
        page.locator('[data-view="spec"]').click()
        expect(page.locator('#references')).to_contain_text('v1')
        expect(page.locator('#references')).to_contain_text('历史引用快照')
        page.locator('[data-view="execution"]').click()
        expect(page.locator('#execution-records')).to_contain_text('验证检查')
        page.locator('#record-filter').select_option('skill')
        expect(page.locator('#execution-records')).not_to_contain_text('验证检查')
        page.locator('#record-filter').select_option('all')
        page.locator('#expand-all').check()
        self.assertEqual(page.locator('.record:not([open])').count(), 0)
        page.locator('#expand-all').uncheck()
        page.locator('#artifacts').click()
        expect(page.locator('#document-preview')).to_contain_text('任务交付总览')
        expect(page.locator('#document-preview')).to_contain_text('不代表真实业务验收')
        page.screenshot(path=str(self.evidence / 'deliverables-overview.png'), full_page=True,
                        animations='disabled')
        page.locator('#deliverable-list button').filter(has_text='当前需求规格').click()
        expect(page.locator('#document-preview')).to_contain_text('<script>')
        self.assertFalse(page.evaluate('Boolean(window.artifactInjected)'))
        page.locator('#deliverable-list button').filter(has_text='验证证据').first.click()
        expect(page.locator('#document-preview')).to_contain_text('value=42')
        page.locator('#deliverable-list button').filter(has_text='归档清单').first.click()
        expect(page.locator('#document-preview')).to_contain_text('files:')
        with page.expect_download() as saved:
            page.get_by_role('button', name='下载全部产物').click()
        downloaded = Path(saved.value.path()).read_text(encoding='utf-8')
        self.assertIn('JSON parsed independently', downloaded)
        self.assertIn('decisions.md', downloaded)
        self.assertNotIn('<script', page.locator('#document-preview').inner_html())
        page.screenshot(path=str(self.evidence / 'deliverables-desktop.png'), full_page=True,
                        animations='disabled')
        page.set_viewport_size({'width': 390, 'height': 844})
        self.assertTrue(page.locator('#modal').evaluate('(n)=>n.scrollWidth <= n.clientWidth + 1'))
        page.screenshot(path=str(self.evidence / 'deliverables-mobile.png'), full_page=True,
                        animations='disabled')
        page.keyboard.press('Escape')
        for width in (1366, 1920, 390):
            page.set_viewport_size({'width': width, 'height': 1000})
            self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'),
                            f'Page overflow at width {width}')
            self.assertTrue(page.evaluate('document.documentElement.scrollHeight <= innerHeight + 1'),
                            f'Page-level vertical scroll at width {width}')
            page.screenshot(path=str(self.evidence / f'workbench-{width}.png'), full_page=True,
                            animations='disabled')
        page.set_viewport_size({'width': 1366, 'height': 640})
        self.assertTrue(page.evaluate('''() => {
            const composer = document.querySelector('.composer').getBoundingClientRect();
            const nav = document.querySelector('.task-sidebar nav').getBoundingClientRect();
            const actions = document.querySelector('.task-actions').getBoundingClientRect();
            return composer.top >= 0 && nav.bottom <= innerHeight &&
                actions.bottom <= innerHeight && document.querySelector('.task-list').clientHeight > 0;
        }'''), 'Compact desktop hides the composer, task list or bottom actions')
        page.screenshot(path=str(self.evidence / 'workbench-1366-compact.png'), full_page=True,
                        animations='disabled')
        page.set_viewport_size({'width': 390, 'height': 1000})
        task_drawer()
        page.screenshot(path=str(self.evidence / 'workbench-mobile-tasks.png'), full_page=True,
                        animations='disabled')
        page.locator('[data-page="skills"]').click()
        expect(page.locator('#skill-list')).to_contain_text('brainstorming')
        page.locator('#skill-list .row').filter(has_text='superpowers/skills/brainstorming/').get_by_role('button').click()
        expect(page.locator('#modal-body')).to_contain_text('.docloop/superpowers/skills/brainstorming/SKILL.md')
        page.screenshot(path=str(self.evidence / 'workbench-mobile-skill-dialog.png'), full_page=True,
                        animations='disabled')
        page.keyboard.press('Escape')
        expect(page.locator('#modal')).not_to_be_visible()
        task_drawer()
        page.locator('[data-page="settings"]').click()
        expect(page.locator('#environment-info')).to_contain_text('sandbox-sqlite')
        task_drawer()
        page.once('dialog', lambda dialog: dialog.accept('浏览器隔离项目'))
        page.locator('#new-project').click()
        task_drawer()
        page.locator('[data-page="workspace"]').click()
        page.locator('[data-view="spec"]').click()
        expect(page.locator('#spec-empty')).to_be_visible()
        new_project = page.locator('#project').input_value()
        self.assertNotEqual(new_project, original_project)
        page.reload()
        task_drawer()
        expect(page.locator('#project')).to_have_value(new_project)
        page.locator('#project').select_option(original_project)
        page.locator('[data-page="workspace"]').click()
        page.locator('[data-view="spec"]').click()
        expect(page.locator('#spec-status')).to_have_text('已批准')
        page.set_viewport_size({'width': 1366, 'height': 1000})
        task_drawer()
        if page.locator('#scrim').is_visible():
            page.keyboard.press('Escape')
        first_task = page.evaluate('window.docloopState.specs.find(s=>s.title==="资料导入与审批").id')
        page.locator('#new-task').click()
        expect(page.locator('#task-title')).to_have_text('请选择任务')
        page.locator('#requirement').fill('独立复核任务\n独立任务的规格和执行记录不能与其他任务混淆。')
        page.locator('#generate').click()
        expect(page.locator('#task-title')).to_have_text('独立复核任务')
        second_task = page.evaluate('window.docloopState.specs.find(s=>s.title==="独立复核任务").id')
        self.assertNotEqual(first_task, second_task)
        page.locator('#task-search').fill('资料导入')
        expect(page.locator('#task-list .task-item')).to_have_count(1)
        page.locator('#task-list .task-item').click()
        page.locator('[data-view="execution"]').click()
        expect(page.locator('#execution-records')).to_contain_text('验证检查')
        page.locator('#task-search').fill('')
        held_execution = []
        execution_pattern = '**/specs/' + second_task + '/execution'
        page.route(execution_pattern, lambda route: held_execution.append(route))
        page.locator('#task-list .task-item').filter(has_text='独立复核任务').click()
        expect(page.locator('#task-title')).to_have_text('独立复核任务')
        expect(page.locator('#execution-records')).not_to_contain_text('验证检查')
        self.assertTrue(held_execution)
        held_execution[0].continue_()
        page.unroute(execution_pattern)
        expect(page.locator('#task-status')).to_have_text('待审批')
        page.locator('#task-list .task-item').filter(has_text='资料导入与审批').click()
        expect(page.locator('#execution-records')).to_contain_text('验证检查')
        held_state = []
        state_pattern = '**/api/state?*'
        page.route(state_pattern, lambda route: held_state.append(route) if not held_state else route.continue_())
        page.evaluate('(id)=>{window.pendingRefresh=refresh(window.docloopState.project_id,id,true);}', first_task)
        page.locator('#task-list .task-item').filter(has_text='独立复核任务').click()
        expect(page.locator('#task-title')).to_have_text('独立复核任务')
        self.assertTrue(held_state)
        held_state[0].continue_()
        page.evaluate('window.pendingRefresh')
        expect(page.locator('#task-title')).to_have_text('独立复核任务')
        page.unroute(state_pattern)
        held_state = []
        page.route(state_pattern, lambda route: held_state.append(route) if not held_state else route.continue_())
        page.evaluate('(id)=>{window.pendingRefresh=refresh(window.docloopState.project_id,id,true);}', second_task)
        page.locator('#new-task').click()
        self.assertTrue(held_state)
        held_state[0].continue_()
        page.evaluate('window.pendingRefresh')
        expect(page.locator('#task-title')).to_have_text('请选择任务')
        page.unroute(state_pattern)
        page.locator('#task-list .task-item').filter(has_text='独立复核任务').click()
        page.locator('[data-view="spec"]').click()
        page.locator('#approve-spec').click()
        page.get_by_role('button', name='确认批准此指纹').click()
        expect(page.locator('#task-status')).to_have_text('待运行')
        page.locator('#scenario').select_option('verification-failure')
        page.locator('#run-spec').click()
        expect(page.locator('#task-status')).to_have_text('阻塞', timeout=30000)
        expect(page.locator('#execution-records .record.error').first).to_be_visible()
        page.screenshot(path=str(self.evidence / 'workbench-blocked.png'), full_page=True,
                        animations='disabled')
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
