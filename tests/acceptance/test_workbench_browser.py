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
            from docloop.workbench import stop_existing
            stop_existing(ROOT, cls.data / 'data', int(cls.url.rsplit(':', 1)[1]))
        cls.process.wait(timeout=15)
        cls.log.close()
        (cls.evidence / 'server.log').write_text(cls.log_path.read_text(encoding='utf-8', errors='replace'), encoding='utf-8')
        cls.temp.cleanup()

    def test_control_toolbar_does_not_overlap_active_view(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.goto(self.url)
        state = page.request.get(self.url + '/api/state').json()
        headers = {'X-DocLoop-Token': state['csrf_token']}
        project = page.request.post(self.url + '/api/projects', headers=headers, data={'name': '布局回归'}).json()
        root = self.url + '/api/projects/' + project['id']
        spec = page.request.post(root + '/specs', headers=headers,
            data={'title': '布局回归', 'requirement': '验证完整运行记录布局', 'mode': 'sandbox'}).json()
        page.request.post(root + '/specs/' + spec['id'] + '/approve', headers=headers,
            data={'sha256': spec['sha256'], 'revision': spec['revision'], 'approver': 'fixture'})
        page.request.post(root + '/specs/' + spec['id'] + '/runs', headers=headers, data={'scenario': 'success'})
        page.goto(self.url + '/?project_id=' + project['id'] + '&task_id=' + spec['id'])
        expect(page.locator('#generate')).to_be_enabled()
        for width in (1366, 1920, 390):
            page.set_viewport_size({'width': width, 'height': 900})
            self.assertTrue(page.evaluate('''() => {
                const bottom = Math.max(...[...document.querySelectorAll('.run-controls button')]
                    .map(node => node.getBoundingClientRect().bottom));
                const view = document.querySelector('.view:not([hidden])').getBoundingClientRect();
                return bottom <= view.top + 1;
            }'''), f'Run controls overlap active view at {width}')

    def test_durable_supplement_and_publication_versions(self):
        page = self.browser.new_page(viewport={'width': 1366, 'height': 900})
        self.addCleanup(page.close)
        page.goto(self.url)
        state = page.request.get(self.url + '/api/state').json()
        headers = {'X-DocLoop-Token': state['csrf_token']}
        project = page.request.post(self.url + '/api/projects', headers=headers, data={'name': '持久工作台验收'}).json()
        page.goto(self.url + '/?project_id=' + project['id'])
        page.locator('[data-page="settings"]').click()
        page.locator('#demo-generation').check()
        page.keyboard.press('Escape')
        page.locator('#requirement').fill('持久资料任务\n需要导出版本化文档')
        page.locator('#generate').click()
        expect(page.locator('#task-title')).to_have_text('持久资料任务')
        expect(page.locator('#save-spec')).to_be_enabled(timeout=10000)
        sid = page.evaluate('window.docloopState.specs[0].id')
        original = page.locator('#spec-content').input_value()
        edited = original + '\n用户未保存的说明\n'
        page.locator('#spec-content').fill(edited)
        for name in ('documents', 'runs', 'skills', 'settings'):
            page.locator('[data-page="' + name + '"]').click()
            expect(page.locator('#auxiliary-modal')).to_be_visible()
            self.assertFalse(page.locator('#workspace').evaluate('(node)=>node.hidden'))
            if name == 'skills':
                expect(page.locator('#skill-list')).to_contain_text('需求规格整理')
                self.assertNotIn('.docloop/', page.locator('#skill-list').inner_text())
            page.keyboard.press('Escape')
            expect(page.locator('#auxiliary-modal')).not_to_be_visible()
            self.assertEqual(edited, page.locator('#spec-content').input_value())
        page.locator('#save-spec').click()
        expect(page.locator('#dirty')).to_have_text('')
        page.reload()
        expect(page.locator('#task-title')).to_have_text('持久资料任务')
        self.assertEqual(1, len(page.request.get(self.url + '/api/state?project_id=' + project['id']).json()['runs']))
        page.locator('#task-supplement').click()
        expect(page.locator('#attach-current-task')).to_be_checked()
        page.locator('#paste-name').fill('补充导出规则.md')
        page.locator('#paste-content').fill('新增要求：导出Markdown并记录版本。')
        page.locator('#add-text').click()
        expect(page.locator('#add-text')).to_be_enabled()
        page.keyboard.press('Escape')
        root = self.url + '/api/projects/' + project['id'] + '/specs/' + sid
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            updates = page.request.get(root + '/updates').json()['updates']
            if updates and updates[0]['status'] == 'waiting_confirmation':
                break
            time.sleep(.1)
        self.assertEqual('waiting_confirmation', updates[0]['status'])
        page.locator('#task-updates').click()
        expect(page.locator('#modal-body')).to_contain_text('新增要求')
        expect(page.locator('#modal-body')).to_contain_text('业务代码功能未确认')
        page.screenshot(path=str(self.evidence / 'supplement-difference.png'), full_page=True, animations='disabled')
        page.keyboard.press('Escape')
        with tempfile.TemporaryDirectory(prefix='docloop-publication-ui-') as directory:
            repo, remote = Path(directory) / 'repo', Path(directory) / 'remote.git'
            subprocess.run(['git', 'init', str(repo)], check=True, capture_output=True)
            subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
            subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@local',
                            'commit', '--allow-empty', '-m', 'fixture'], check=True, capture_output=True)
            subprocess.run(['git', '-C', str(repo), 'remote', 'add', 'origin', str(remote)], check=True, capture_output=True)
            bound = page.request.post(self.url + '/api/projects/' + project['id'] + '/repository',
                headers=headers, data={'path': str(repo)})
            self.assertEqual(200, bound.status)
            page.locator('#refresh').click()
            expect(page.locator('#refresh')).to_be_enabled()
            page.locator('#artifacts').click()
            page.get_by_role('button', name='Git 版本与上传').click()
            page.get_by_role('button', name='冻结产物并本地提交').click()
            expect(page.locator('#modal-body')).to_contain_text('已本地提交，待上传', timeout=20000)
            page.get_by_role('button', name='上传 / 重试此版本').click()
            expect(page.locator('#modal-body')).to_contain_text('远端分支与标签已确认', timeout=20000)
            page.screenshot(path=str(self.evidence / 'publication-confirmed.png'), full_page=True, animations='disabled')
            page.get_by_role('button', name='查看版本索引').click()
            expect(page.locator('#modal-body')).to_contain_text('产物版本索引')
            page.get_by_role('button', name='返回版本列表').click()
            page.get_by_role('button', name='查看版本清单').click()
            expect(page.locator('#modal-body')).to_contain_text('source_code_commit')
            expect(page.locator('#modal-body')).to_contain_text('sha256')

    def test_full_browser_flow_layout_and_refresh(self):
        page = self.browser.new_page(viewport={'width': 1366, 'height': 1000})
        self.addCleanup(page.close)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        page.goto(self.url)
        def navigate(name):
            if page.locator('#auxiliary-modal').is_visible():
                page.locator('#auxiliary-modal .dialog-close').click()
            toggle = page.locator('#drawer-toggle')
            if toggle.is_visible() and toggle.get_attribute('aria-expanded') != 'true':
                toggle.click()
            page.locator('[data-page="' + name + '"]').click()
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
        page.locator('#requirement').fill('未配置模型的明确提示')
        page.locator('#generate').click()
        expect(page.locator('#notice')).to_contain_text('当前模型未配置')
        page.locator('#requirement').fill('')
        navigate('settings')
        page.locator('#api-key').fill('browser-test-private-key')
        page.locator('#demo-generation').check()
        self.assertEqual(page.locator('#api-key').input_value(), 'browser-test-private-key')
        page.get_by_role('button', name='保存模型配置').click()
        expect(page.locator('#notice')).to_contain_text('模型配置已保存')
        page.reload()
        expect(page.locator('#active-model')).to_have_value('deepseek-v4.1-flash')
        self.assertTrue(page.evaluate('window.docloopState.environment.model.has_api_key'))
        self.assertEqual(page.locator('#api-key').input_value(), '')
        page.locator('#active-model').select_option('gpt-6.1-sol')
        expect(page.locator('#active-model')).to_be_enabled()
        self.assertEqual(page.locator('#generation-mode').count(), 0)
        self.assertEqual(page.locator('.composer-tools #active-model').count(), 1)
        navigate('settings')
        page.locator('#demo-generation').check()
        navigate('workspace')
        self.assertTrue(page.evaluate("CSS.supports('appearance', 'base-select')"))
        expect(page.locator('#active-model')).to_have_css('appearance', 'base-select')
        page.locator('#active-model').click()
        page.screenshot(path=str(self.evidence / 'model-select-open.png'), full_page=True, animations='disabled')
        page.keyboard.press('ArrowDown')
        page.keyboard.press('Enter')
        expect(page.locator('#active-model')).to_have_value('deepseek-v4.1-flash')
        expect(page.locator('#active-model')).to_be_enabled()
        page.locator('#active-model').select_option('gpt-6.1-sol')
        expect(page.locator('#active-model')).to_be_enabled()
        def task_drawer():
            if page.locator('#auxiliary-modal').is_visible():
                page.locator('#auxiliary-modal .dialog-close').click()
            toggle = page.locator('#drawer-toggle')
            if toggle.is_visible() and toggle.get_attribute('aria-expanded') != 'true':
                toggle.click()
        original_project = page.locator('#project').input_value()
        page.locator('#generate').click()
        expect(page.locator('#notice')).to_contain_text('请填写')
        navigate('documents')
        page.locator('#paste-name').fill('审批来源-长名称-用于验证行号和版本.md')
        page.locator('#paste-content').fill('项目资料导入后必须人工审批。\n审批需要保留Spec版本、来源和指纹。')
        page.locator('#add-text').click()
        expect(page.locator('#document-list')).to_contain_text('审批来源')
        navigate('workspace')
        self.assertEqual(page.locator('#spec-title').count(), 0)
        expect(page.locator('#active-model option')).to_have_count(2)
        page.locator('#requirement').fill('资料导入与审批\n导入项目资料并审批Spec，保留来源与版本。')
        page.locator('#generate').click()
        expect(page.locator('#spec-detail')).to_be_visible()
        expect(page.locator('#save-spec')).to_be_enabled(timeout=10000)
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
        expect(page.locator('#spec-revision')).to_contain_text('3')
        page.unroute('**/api/projects/*/specs/*')
        page.locator('#approve-spec').click()
        expect(page.locator('#modal')).to_be_visible()
        page.locator('#approver').fill('浏览器沙箱测试')
        page.get_by_role('button', name='确认批准此指纹').click()
        expect(page.locator('#spec-status')).to_have_text('已批准')
        page.locator('#run-spec').click()
        expect(page.locator('#run-spec')).to_be_enabled(timeout=30000)
        navigate('runs')
        expect(page.locator('#run-list')).to_contain_text('accepted')
        expect(page.locator('#run-list')).to_contain_text('非真实业务验收')
        page.reload()
        page.locator('[data-view="spec"]').click()
        expect(page.locator('#spec-status')).to_have_text('已批准')
        expect(page.locator('#spec-content')).to_have_value(edited)
        navigate('documents')
        page.locator('#paste-name').fill('审批来源-长名称-用于验证行号和版本.md')
        page.locator('#paste-content').fill('新版资料：不同于旧版的业务内容。')
        page.locator('#add-text').click()
        expect(page.locator('#document-list')).to_contain_text('版本 2')
        navigate('workspace')
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
        navigate('skills')
        expect(page.locator('#skill-list')).to_contain_text('需求与方案分析')
        page.locator('#skill-list .row').filter(has_text='需求与方案分析').get_by_role('button').click()
        expect(page.locator('#modal-body')).to_contain_text('澄清目标、比较方案并形成设计')
        page.screenshot(path=str(self.evidence / 'workbench-mobile-skill-dialog.png'), full_page=True,
                        animations='disabled')
        page.keyboard.press('Escape')
        expect(page.locator('#modal')).not_to_be_visible()
        task_drawer()
        navigate('settings')
        expect(page.locator('#environment-info')).to_contain_text('sandbox-sqlite')
        task_drawer()
        page.once('dialog', lambda dialog: dialog.accept('浏览器隔离项目'))
        page.locator('#new-project').click()
        task_drawer()
        navigate('workspace')
        page.locator('[data-view="spec"]').click()
        expect(page.locator('#spec-empty')).to_be_visible()
        new_project = page.locator('#project').input_value()
        self.assertNotEqual(new_project, original_project)
        page.reload()
        task_drawer()
        expect(page.locator('#project')).to_have_value(new_project)
        page.locator('#project').select_option(original_project)
        navigate('workspace')
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
        # 真实浏览器→异步Run→本地HTTP夹具等待→取消；绝不连接外部模型。
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from threading import Event, Thread
        entered, release = Event(), Event()
        class Provider(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length', '0')))
                entered.set()
                release.wait(8)
                try:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{}')
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return  # 取消HTTP等待后，夹具连接已关闭。
            def log_message(self, *args):
                return
        provider = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
        provider.daemon_threads = True
        server_thread = Thread(target=provider.serve_forever, daemon=True)
        server_thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix='docloop-ui-repo-') as target:
                subprocess.run(['git', '-C', target, 'init'], check=True, capture_output=True)
                subprocess.run(['git', '-C', target, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@local',
                    'commit', '--allow-empty', '-m', 'fixture'], check=True, capture_output=True)
                navigate('settings')
                page.locator('#model').select_option('deepseek-v4.1-flash')
                expect(page.locator('#model')).to_be_enabled()
                page.locator('#base-url').fill(f'http://127.0.0.1:{provider.server_port}')
                page.locator('#api-key').fill('local-fixture-key')
                page.get_by_role('button', name='保存模型配置').click()
                expect(page.locator('#notice')).to_contain_text('模型配置已保存')
                page.locator('#repository-path').fill(target)
                page.locator('#register-repository').click()
                expect(page.locator('#start-runtime')).to_be_enabled()
                page.locator('#start-runtime').click()
                expect(page.locator('#cancel-runtime')).to_be_enabled()
                self.assertTrue(entered.wait(3))
                page.locator('#cancel-runtime').click()
                expect(page.locator('#runtime-status')).to_contain_text('取消')
                expect(page.locator('#task-status')).to_have_text('已取消', timeout=3000)
                page.screenshot(path=str(self.evidence / 'runtime-cancelled.png'), full_page=True, animations='disabled')
        finally:
            release.set()
            provider.shutdown()
            provider.server_close()
            server_thread.join(timeout=5)
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
