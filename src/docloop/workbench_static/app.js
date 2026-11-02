'use strict';

const $ = id => document.getElementById(id);
let state = null;
let selected = null;
let epoch = 0;
let busy = 0;
const drafts = new Map();

let execution = null;
let executionEpoch = 0;
let activeView = 'execution';
let pollTimer = null;
let runPending = false;
let noticeTimer = null;
const recordExpansion = new Map();

const titles = {
  workspace: ['任务执行', '等待任务'],
  documents: ['资料库', '资料与检索'],
  runs: ['运行记录', '沙箱运行记录'],
  skills: ['本地 Skills', '本地 Skills'],
  settings: ['设置', '设置'],
};
const statusNames = {
  draft: '待审批', approved: '待运行', in_progress: '执行中',
  accepted: '已通过', blocked: '阻塞', failed: '失败',
};
const taskMarks = {
  draft: '○', approved: '●', in_progress: '◐', accepted: '✓', blocked: '!', failed: '!',
};
const stageNames = ['需求规格', '版本审批', '受控验证', '结果归档'];
const resultNames = {
  draft: '待审', ready: '就绪', in_progress: '执行中', implemented: '已实现',
  verified: '已验证', accepted: '已通过', passed: '通过', failed: '失败',
  blocked: '阻塞', loaded: '已加载', recorded: '已记录', error: '错误',
  approved: '已批准', cancelled: '已取消', interrupted: '已中断',
  active: '可检索', inactive: '已停用', superseded: '已替换',
};
const recordIcons = {
  stage: 'M12 4l6 8-6 8-6-8z',
  skill: 'm9 7-4 5 4 5M15 7l4 5-4 5',
  verification: 'M4 12l5 5L20 6',
  error: 'M12 4l9 16H3zM12 10v4M12 17v.5',
};

function el(tag, text, cls) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (cls) node.className = cls;
  return node;
}
function icon(path, cls = '') {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '1.8');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');
  if (cls) svg.setAttribute('class', cls);
  const shape = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  shape.setAttribute('d', path);
  svg.append(shape);
  return svg;
}
function notice(message, error = false) {
  clearTimeout(noticeTimer);
  $('notice-text').textContent = message;
  $('notice').className = error ? 'notice error' : 'notice';
  $('notice').hidden = !message;
  if (message && !error) {
    noticeTimer = setTimeout(() => { $('notice').hidden = true; }, 6000);
  }
}
function empty(target, message) {
  target.replaceChildren(el('div', message, 'empty'));
}
function dirty() {
  return selected && $('spec-content').value !== selected.content;
}
function allowLeave() {
  if (!dirty()) return true;
  if (!confirm('当前规格有未保存的修改。确定放弃这些修改吗？')) return false;
  drafts.delete(selected.id);
  $('spec-content').value = selected.content;
  return true;
}
function formatTime(value) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) :
    new Intl.DateTimeFormat('zh-CN', {timeZone: 'Asia/Shanghai', dateStyle: 'short', timeStyle: 'medium'}).format(date);
}
async function api(path, options = {}) {
  const headers = {'Content-Type': 'application/json', ...options.headers};
  if (options.method && options.method !== 'GET') headers['X-DocLoop-Token'] = state?.csrf_token || '';
  const response = await fetch(path, {...options, headers});
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error('服务响应无法读取，请稍后重试。');
  }
  if (!response.ok) throw new Error(body.detail || `请求失败（${response.status}）`);
  return body;
}
async function action(fn, button) {
  if (button?.disabled) return;
  busy++;
  if (button) button.disabled = true;
  syncButtons();
  try {
    await fn();
  } catch (error) {
    const message = error.message || '操作失败，请重试。';
    notice(message, true);
    if ($('modal').open) {
      let target = $('modal-error');
      if (!target) {
        target = el('p', undefined, 'error');
        target.id = 'modal-error';
        target.setAttribute('role', 'alert');
        $('modal-body').append(target);
      }
      target.textContent = message;
    }
  } finally {
    busy--;
    if (button) button.disabled = false;
    syncButtons();
  }
}
function projectPath() {
  if (!state?.project_id) throw new Error('请先新建或选择一个项目。');
  return '/api/projects/' + encodeURIComponent(state.project_id);
}

async function refresh(projectId, preferredSpec, silent = false) {
  if (dirty()) drafts.set(selected.id, $('spec-content').value);
  executionEpoch++;
  const ticket = ++epoch;
  const previousId = preferredSpec || selected?.id || new URL(location.href).searchParams.get('task_id');
  if (!silent) notice('正在加载任务…');
  const data = await api('/api/state' + (projectId ? '?project_id=' + encodeURIComponent(projectId) : ''));
  if (ticket !== epoch) return;
  const oldId = selected?.id;
  state = data;
  selected = data.specs.find(spec => spec.id === previousId) || data.specs[0] || null;
  if (selected?.id !== oldId) execution = null;
  render();
  updateUrl();
  if (!silent) notice('');
  await loadExecution();
}

function listRow() {
  const node = el('div', undefined, 'row list-row');
  return node;
}
function fillList(target, values, make, message) {
  target.replaceChildren();
  if (!values?.length) return empty(target, message);
  values.forEach(value => target.append(make(value)));
}

function render() {
  const projectSelect = $('project');
  projectSelect.replaceChildren();
  state.projects.forEach(project => {
    const option = el('option', project.name);
    option.value = project.id;
    projectSelect.append(option);
  });
  projectSelect.value = state.project_id || '';
  projectSelect.title = state.projects.find(project => project.id === state.project_id)?.name || '';

  const activeDocs = state.documents.filter(doc => doc.status === 'active');
  $('doc-count').textContent = String(activeDocs.length);
  fillList($('context-docs'), activeDocs, doc => {
    const node = listRow();
    node.append(el('strong', doc.name), el('small', `版本 ${doc.version} · 可检索`));
    return node;
  }, '暂无启用的项目资料');
  fillList($('document-list'), state.documents, doc => {
    const node = listRow();
    node.append(
      el('strong', doc.name),
      el('small', `版本 ${doc.version} · ${doc.status === 'active' ? '可检索' : '已停用'} · ${formatTime(doc.created_at)}`),
      el('code', doc.content_hash),
    );
    const actions = el('div', undefined, 'doc-actions');
    const remove = el('button', '停用资料');
    remove.type = 'button';
    remove.disabled = doc.status !== 'active';
    remove.addEventListener('click', () => {
      askConfirm('停用资料', `确定停用“${doc.name}”？停用后不再参与新检索，历史引用仍保留。`, '停用资料', () => {
        action(async () => {
          const pid = state.project_id;
          await api(projectPath() + '/documents/' + encodeURIComponent(doc.id), {method: 'DELETE'});
          if (state.project_id === pid) {
            await refresh(pid);
            notice(`已停用「${doc.name}」，历史引用仍保留。`);
          }
        }, remove);
      });
    });
    if (doc.status === 'active') {
      actions.append(remove);
      node.append(actions);
    }
    return node;
  }, '资料库为空，添加文件或粘贴文本。');

  renderSpec();
  renderRuns();
  renderSettings();
  renderTasks();
  renderTaskHeader();
  syncButtons();
}

function renderSettings() {
  const model = state.environment.model || {};
  const real = $('generation-mode').querySelector('[value="real"]');
  real.disabled = !model.configured;
  real.textContent = model.configured ? '真实模型生成' : '真实模型（未配置）';
  if (!model.configured) $('generation-mode').value = 'sandbox';
  $('base-url').value = model.base_url || '';
  $('model').value = model.model || '';
  const oracle = state.environment.oracle?.configured;
  $('storage-pill').textContent = oracle ? 'Oracle 关系存储' : 'SQLite 沙箱';
  $('model-pill').textContent = model.configured ? '真实模型已配置' : '模型未配置';
  const info = $('environment-info');
  info.replaceChildren();
  [
    ['存储', state.environment.storage_backend === 'oracle' ? 'Oracle 关系存储' :
      `SQLite 沙箱（${state.environment.storage_backend}）`],
    ['数据目录', state.environment.data_root],
    ['模型配置', model.configured ? '已配置（连接以测试结果为准）' : '未配置'],
    ['Oracle', oracle ? '已配置（真实环境验收另行记录）' : '未配置'],
  ].forEach(([key, value]) => info.append(el('dt', key), el('dd', value)));
}

function renderSpec() {
  $('spec-empty').hidden = !!selected;
  $('spec-detail').hidden = !selected;
  $('references').replaceChildren();
  if (!selected) return empty($('references'), '选择规格后查看引用');

  $('spec-content').value = drafts.get(selected.id) ?? selected.content;
  $('spec-content').readOnly = selected.status === 'approved';
  $('spec-status').textContent = selected.status === 'approved' ? '已批准' : '待审批';
  $('spec-status').dataset.status = selected.status === 'approved' ? 'accepted' : 'draft';
  $('spec-revision').textContent = '修订 ' + selected.revision;
  $('spec-mode').textContent = selected.generation_mode === 'real' ? '真实模型生成' : '沙箱生成';
  $('spec-hash').textContent = selected.sha256;
  $('dirty').textContent = dirty() ? '· 保留了未保存的本地修改' : '';

  fillList($('references'), selected.references, reference => {
    const current = state.documents.find(doc => doc.id === reference.document_id);
    const node = listRow();
    node.append(
      el('strong', reference.name + ` · v${reference.version} · L${reference.line_start}–${reference.line_end}`),
      el('small', reference.text),
      el('code', reference.content_hash || ''),
      el('small', current?.status === 'active' ? '引用快照 · 当前可检索' : '历史引用快照 · 此版本已不参与当前检索'),
    );
    return node;
  }, '当前规格暂无引用');

  fillList($('skill-sources'), selected.skill_sources, source => {
    const node = listRow();
    node.append(el('strong', source.ref), el('small', source.path + ' · ' + source.sha256));
    return node;
  }, '未记录 Skill 来源');
  syncButtons();
}

function renderRuns() {
  fillList($('run-list'), state.runs, run => {
    const node = listRow();
    const heading = el('div', undefined, 'run-heading');
    heading.append(el('strong', run.id), el('span', statusNames[run.status] || run.status, 'pill'));
    node.append(heading, el('small', `${run.status} · ${run.mode} · ${formatTime(run.created_at)}`));
    node.append(el('p', '沙箱演示 · 非真实业务验收', 'muted small'));
    const history = el('pre', typeof run.result?.history === 'string' ? run.result.history :
      JSON.stringify(run.result?.history || [], null, 2));
    node.append(history);
    if (run.result?.error) {
      node.append(el('pre', typeof run.result.error === 'string' ? run.result.error :
        JSON.stringify(run.result.error, null, 2)));
    }
    if (run.result?.archive) {
      const details = el('details');
      details.append(el('summary', '归档结果'), el('pre', JSON.stringify(run.result.archive, null, 2)));
      node.append(details);
    }
    return node;
  }, '暂无运行记录。批准规格后即可运行沙箱验证。');
}

function modal(title, nodes, actions = []) {
  $('modal-title').textContent = title;
  $('modal-body').replaceChildren(...nodes);
  $('modal-actions').replaceChildren(...actions);
  $('modal').showModal();
  const target = $('modal-body').querySelector('input:not([type="hidden"]), textarea, select') ||
    $('modal-actions').querySelector('.primary, button') ||
    $('modal').querySelector('.dialog-close');
  target?.focus();
}
function makeButton(text, handler, primary = false) {
  const button = el('button', text, primary ? 'primary' : '');
  button.type = 'button';
  button.addEventListener('click', () => action(() => handler(button), button));
  return button;
}
function askConfirm(title, message, confirmLabel, onConfirm) {
  const cancel = el('button', '取消');
  cancel.type = 'button';
  cancel.addEventListener('click', () => $('modal').close());
  const accept = el('button', confirmLabel, 'primary');
  accept.type = 'button';
  accept.addEventListener('click', () => {
    $('modal').close();
    onConfirm();
  });
  modal(title, [el('p', message)], [cancel, accept]);
}
async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.append(area);
    area.select();
    const copied = document.execCommand('copy');
    area.remove();
    return copied;
  }
}

function taskStatus(spec) {
  return state?.task_summaries?.[spec?.id]?.status || spec?.status || 'draft';
}
function updateUrl() {
  const url = new URL(location.href);
  if (state?.project_id) url.searchParams.set('project_id', state.project_id);
  if (selected) url.searchParams.set('task_id', selected.id);
  else url.searchParams.delete('task_id');
  history.replaceState(null, '', url);
}
function syncButtons() {
  const approved = selected?.status === 'approved';
  $('save-spec').disabled = !selected || approved || busy > 0;
  $('approve-spec').disabled = !selected || approved || dirty() || busy > 0;
  $('run-spec').disabled = !approved || dirty() || busy > 0;
  $('generate').disabled = !state?.project_id || busy > 0;
  $('project').disabled = busy > 0;
  $('new-project').disabled = busy > 0;
  $('new-task').disabled = busy > 0;
  document.querySelectorAll('.task-item').forEach(item => { item.disabled = busy > 0; });
  ['spec-title', 'requirement', 'generation-mode'].forEach(id => { $(id).disabled = busy > 0; });
  $('spec-content').readOnly = busy > 0 || approved;
  $('artifacts').disabled = !execution?.artifacts?.length || busy > 0;
  $('copy-hash').disabled = !selected || busy > 0;
  ['upload', 'add-text', 'search', 'test-model'].forEach(id => { $(id).disabled = busy > 0; });
  ['record-filter', 'expand-all'].forEach(id => { $(id).disabled = !selected || busy > 0; });
  $('busy-status').hidden = busy === 0;
  $('main').setAttribute('aria-busy', String(busy > 0));
}

function renderTaskHeader() {
  const status = selected ? taskStatus(selected) : null;
  $('task-title').textContent = selected?.title || '请选择任务';
  $('task-title').title = selected?.title || '';
  $('task-status').textContent = statusNames[status] || status || '';
  $('task-status').dataset.status = status || '';
  $('execution-boundary').textContent =
    '受控沙箱验证不代表真实业务验收 · ' + (state?.environment.oracle?.configured ? 'Oracle关系存储已配置' : 'SQLite沙箱');
  $('bottom-status').textContent = selected ? `当前任务 · ${statusNames[status] || status}` : '等待创建或选择任务';

  const latest = state?.task_summaries?.[selected?.id];
  const archived = !!execution?.runs?.find(run => run.id === latest?.id)?.result?.archive;
  const flags = [!!selected, selected?.status === 'approved', latest?.status === 'accepted', archived];
  $('stage-count').textContent = flags.filter(Boolean).length + '/4';
  const current = selected ? flags.findIndex(flag => !flag) : -1;
  const list = $('stage-list');
  list.replaceChildren();
  stageNames.forEach((name, index) => {
    const done = flags[index];
    const item = el('li', undefined, 'step' + (done ? ' done' : '') + (index === current ? ' current' : ''));
    item.append(
      el('span', done ? '✓' : '○', 'step-dot'),
      el('span', name, 'step-name'),
      el('span', done ? '已完成' : '待完成', 'step-state'),
    );
    list.append(item);
  });
}

function renderTasks() {
  const previousScroll = $('task-list').scrollTop;
  const query = $('task-search').value.trim().toLowerCase();
  const specs = (state?.specs || []).filter(spec => spec.title.toLowerCase().includes(query));
  const all = state?.specs || [];
  const done = all.filter(spec => taskStatus(spec) === 'accepted').length;
  const running = all.filter(spec => taskStatus(spec) === 'in_progress').length;
  const blocked = all.filter(spec => ['blocked', 'failed'].includes(taskStatus(spec))).length;
  const waiting = all.filter(spec => ['draft', 'approved'].includes(taskStatus(spec))).length;
  const parts = [`已完成 ${done} / ${all.length}`];
  if (running) parts.push(`执行中 ${running}`);
  if (blocked) parts.push(`阻塞 ${blocked}`);
  if (waiting) parts.push(`待处理 ${waiting}`);
  $('task-summary').textContent = all.length ? parts.join(' · ') : '暂无任务';
  fillList($('task-list'), specs, spec => {
    const status = taskStatus(spec);
    const button = el('button', undefined, 'task-item' + (spec.id === selected?.id ? ' active' : ''));
    button.type = 'button';
    button.title = spec.title;
    button.dataset.status = status;
    button.setAttribute('aria-current', spec.id === selected?.id ? 'true' : 'false');
    button.append(
      el('span', taskMarks[status] || '○', 'task-mark'),
      el('span', spec.title, 'task-name'),
      el('span', statusNames[status] || status, 'task-label'),
    );
    button.disabled = busy > 0;
    button.addEventListener('click', () => {
      if (busy || !allowLeave()) return;
      epoch++;
      clearTimeout(pollTimer);
      selected = spec;
      execution = null;
      executionEpoch++;
      renderSpec();
      renderTasks();
      renderTaskHeader();
      renderExecution();
      $('execution-records').scrollTop = 0;
      updateUrl();
      setPage('workspace');
      closeDrawer();
      action(loadExecution);
    });
    return button;
  }, query ? '未找到匹配任务' : '暂无任务，在下方描述需求开始。');
  $('task-list').scrollTop = previousScroll;
}

function setView(view) {
  activeView = view;
  $('execution-view').hidden = view !== 'execution';
  $('spec-view').hidden = view !== 'spec';
  document.querySelectorAll('[data-view]').forEach(button =>
    button.setAttribute('aria-selected', String(button.dataset.view === view)));
}
function setPage(page) {
  document.querySelectorAll('.page').forEach(node => { node.hidden = node.id !== page; });
  document.querySelectorAll('[data-page]').forEach(button =>
    button.classList.toggle('active', button.dataset.page === page));
  const title = page === 'workspace' ? titles.workspace[0] : titles[page][0];
  $('page-title').textContent = title;
  document.title = `DocLoop · ${title}`;
}

async function loadExecution() {
  clearTimeout(pollTimer);
  const ticket = ++executionEpoch;
  const pid = state?.project_id;
  const sid = selected?.id;
  if (!sid) {
    execution = null;
    empty($('execution-records'), '选择任务后查看实际执行记录。');
    syncButtons();
    return;
  }
  const result = await api('/api/projects/' + encodeURIComponent(pid) +
    '/specs/' + encodeURIComponent(sid) + '/execution');
  if (ticket !== executionEpoch || pid !== state?.project_id || sid !== selected?.id) return;
  execution = result;
  renderExecution();
  renderTaskHeader();
  syncButtons();
  if (taskStatus(selected) === 'in_progress' || runPending) schedulePoll(pid, sid);
}
function schedulePoll(pid, sid) {
  pollTimer = setTimeout(() => {
    if (pid !== state?.project_id || sid !== selected?.id) return;
    if (document.hidden) {
      schedulePoll(pid, sid);
      return;
    }
    refresh(pid, sid, true).catch(error => notice(error.message, true));
  }, 800);
}

function recordNode(record) {
  const key = (selected?.id || '') + ':' + record.id;
  const details = el('details', undefined, 'record' + (record.type === 'error' ? ' error' : ''));
  details.dataset.recordKey = key;
  details.open = recordExpansion.has(key) ? recordExpansion.get(key) : $('expand-all').checked;
  details.addEventListener('toggle', () => recordExpansion.set(key, details.open));

  const summary = el('summary');
  const iconNode = el('span', undefined, 'record-icon');
  iconNode.append(icon(recordIcons[record.type] || recordIcons.stage));
  const title = el('span', record.title, 'record-title');
  const briefText = resultNames[record.summary] || record.summary || '';
  const brief = el('span', briefText, 'record-summary');
  summary.append(iconNode, title, brief);
  const raw = record.result === undefined || record.result === null ? '' :
    (typeof record.result === 'string' ? record.result : JSON.stringify(record.result));
  if (raw) {
    const label = resultNames[raw] || raw;
    const result = el('span', label.length > 32 ? label.slice(0, 32) + '…' : label, 'record-result');
    result.dataset.result = raw;
    result.title = raw;
    summary.append(result);
  }
  const time = formatTime(record.created_at);
  if (time) summary.append(el('span', time, 'record-time'));
  details.append(summary);
  details.append(el('pre', record.detail || '该记录没有更多详情。'));
  if (record.run_id) details.append(el('code', '运行：' + record.run_id));
  return details;
}

function renderExecution() {
  const box = $('execution-records');
  const scrollTop = box.scrollTop;
  const filter = $('record-filter').value;
  const records = (execution?.records || []).filter(record =>
    filter === 'all' || record.type === filter ||
    (filter === 'exception' && ['verification', 'error'].includes(record.type)));
  $('record-scope').textContent = (execution?.record_scope || '最近20次运行') +
    ` 仅显示实际执行记录，不展示模型推理；当前 ${records.length} 条。沙箱结果不代表真实业务验收。`;
  $('locate-error').hidden = !records.some(record => record.type === 'error');
  box.replaceChildren();
  if (!records.length) {
    empty(box, '当前筛选下暂无执行记录。审批规格后可运行沙箱验证。');
  } else {
    let lastRun = null;
    records.forEach(record => {
      if (record.run_id && record.run_id !== lastRun) {
        const run = execution?.runs?.find(item => item.id === record.run_id);
        const group = el('div', undefined, 'record-group');
        group.append(el('span', `运行 ${record.run_id.slice(0, 8)}…`, 'record-group-id'));
        if (run) {
          const pill = el('span', statusNames[run.status] || run.status, 'pill');
          pill.dataset.status = run.status;
          group.append(pill);
          const time = formatTime(run.created_at);
          if (time) group.append(el('span', time, 'record-group-time'));
        }
        box.append(group);
        lastRun = record.run_id;
      }
      box.append(recordNode(record));
    });
  }
  box.scrollTop = scrollTop;
}

function closeDrawer() {
  document.body.classList.remove('drawer-open');
  $('scrim').hidden = true;
  $('drawer-toggle').setAttribute('aria-expanded', 'false');
}

/* ---------- 事件绑定 ---------- */
$('project').addEventListener('change', () => {
  if (!allowLeave()) {
    $('project').value = state.project_id;
    return;
  }
  const pid = $('project').value;
  selected = null;
  $('search-results').replaceChildren();
  action(() => refresh(pid));
});
$('refresh').addEventListener('click', () => action(() => refresh(state?.project_id), $('refresh')));
$('file').addEventListener('change', () => {
  $('file-name').textContent = $('file').files[0]?.name || '未选择文件';
});
$('new-project').addEventListener('click', () => {
  if (!allowLeave()) return;
  const name = prompt('新项目名称');
  if (name?.trim()) {
    action(async () => {
      if (name.trim().length > 120) throw new Error('项目名称最多 120 个字符。');
      const project = await api('/api/projects', {method: 'POST', body: JSON.stringify({name: name.trim()})});
      selected = null;
      await refresh(project.id);
      notice(`已创建项目「${project.name}」。`);
    }, $('new-project'));
  }
});
$('spec-content').addEventListener('input', () => {
  if (selected) {
    if (dirty()) drafts.set(selected.id, $('spec-content').value);
    else drafts.delete(selected.id);
  }
  $('dirty').textContent = dirty() ? '· 尚未保存' : '';
  syncButtons();
});
$('generate').addEventListener('click', () => action(async () => {
  if (!allowLeave()) return;
  const requirement = $('requirement').value.trim();
  const title = $('spec-title').value.trim() || requirement.split('\n')[0].slice(0, 80);
  if (!requirement) throw new Error('请填写新任务需求。');
  const pid = state.project_id;
  const spec = await api(projectPath() + '/specs', {
    method: 'POST',
    body: JSON.stringify({title, requirement, mode: $('generation-mode').value}),
  });
  if (state.project_id === pid) {
    await refresh(pid, spec.id);
    $('spec-title').value = '';
    $('requirement').value = '';
    setPage('workspace');
    setView('spec');
    closeDrawer();
  }
}, $('generate')));
$('save-spec').addEventListener('click', () => action(async () => {
  const pid = state.project_id;
  const sid = selected.id;
  const saved = await api(projectPath() + '/specs/' + encodeURIComponent(sid), {
    method: 'PUT',
    body: JSON.stringify({content: $('spec-content').value, revision: selected.revision}),
  });
  drafts.delete(sid);
  if (selected?.id === sid) {
    selected = saved;
    $('spec-content').value = saved.content;
  }
  if (state.project_id === pid) {
    await refresh(pid, sid);
    notice(`规格已保存（修订 ${saved.revision}）。`);
  }
}, $('save-spec')));
$('approve-spec').addEventListener('click', () => {
  if (!selected || dirty()) return;
  const spec = selected;
  const pid = state.project_id;
  const description = el('p', '确认批准当前版本后，该规格将锁定。请核对以下 SHA-256：');
  const meta = el('p', `修订 ${spec.revision} · ${spec.generation_mode === 'real' ? '真实模型生成' : '沙箱生成'}`, 'muted small');
  const hash = el('code', spec.sha256);
  const label = el('label', '审批人');
  label.htmlFor = 'approver';
  const input = el('input');
  input.id = 'approver';
  input.maxLength = 120;
  input.value = '本机用户';
  modal('审批当前规格', [description, meta, hash, label, input], [makeButton('确认批准此指纹', async () => {
    const approver = input.value.trim();
    if (!approver) throw new Error('请填写审批人。');
    await api('/api/projects/' + encodeURIComponent(pid) + '/specs/' + encodeURIComponent(spec.id) + '/approve', {
      method: 'POST',
      body: JSON.stringify({sha256: spec.sha256, revision: spec.revision, approver}),
    });
    $('modal').close();
    if (state.project_id === pid) {
      await refresh(pid, spec.id);
      notice('已审批当前规格指纹，规格已锁定。');
    }
  }, true)]);
});
$('run-spec').addEventListener('click', () => action(async () => {
  setPage('workspace');
  setView('execution');
  closeDrawer();
  const button = $('run-spec');
  const runLabel = button.textContent;
  button.textContent = '运行中…';
  const pid = state.project_id;
  const sid = selected.id;
  runPending = true;
  loadExecution().catch(error => notice(error.message, true));
  try {
    await api(projectPath() + '/specs/' + encodeURIComponent(sid) + '/runs', {
      method: 'POST',
      body: JSON.stringify({scenario: $('scenario').value}),
    });
  } finally {
    runPending = false;
    clearTimeout(pollTimer);
    button.textContent = runLabel;
  }
  if (state.project_id === pid && selected?.id === sid) {
    await refresh(pid, sid);
    const outcome = taskStatus(selected);
    if (outcome === 'blocked' || outcome === 'failed') {
      notice(`沙箱验证返回${statusNames[outcome]}，已定位到异常记录。`, true);
      $('execution-records').querySelector('.record.error')?.scrollIntoView({block: 'center', behavior: 'smooth'});
    } else {
      notice('沙箱验证已返回，执行记录与产物已更新。');
      const box = $('execution-records');
      requestAnimationFrame(() => { box.scrollTop = box.scrollHeight; });
    }
  }
}, $('run-spec')));

async function addDocument(payload) {
  const pid = state.project_id;
  const result = await api(projectPath() + '/documents', {method: 'POST', body: JSON.stringify(payload)});
  if (state.project_id === pid) {
    await refresh(pid);
    notice(result.deduplicated ? '已识别相同内容，复用已有资料。' : '资料已添加。');
  }
}
$('upload').addEventListener('click', () => action(async () => {
  const file = $('file').files[0];
  if (!file) throw new Error('请先选择文件。');
  if (!/\.(md|txt)$/i.test(file.name) || file.size > 2 * 1024 * 1024) {
    throw new Error('仅支持不超过 2 MiB 的 .md / .txt 文件。');
  }
  const bytes = new Uint8Array(await file.arrayBuffer());
  try {
    new TextDecoder('utf-8', {fatal: true}).decode(bytes);
  } catch {
    throw new Error('文件必须采用 UTF-8 编码。');
  }
  let binary = '';
  for (let index = 0; index < bytes.length; index += 8192) {
    binary += String.fromCharCode(...bytes.subarray(index, index + 8192));
  }
  await addDocument({name: file.name, data_base64: btoa(binary)});
  $('file').value = '';
  $('file-name').textContent = '未选择文件';
}, $('upload')));
$('add-text').addEventListener('click', () => action(async () => {
  const name = $('paste-name').value.trim();
  const content = $('paste-content').value;
  if (!/\.(md|txt)$/i.test(name) || !content.trim()) throw new Error('请填写 .md / .txt 文件名和文本内容。');
  if (new TextEncoder().encode(content).length > 2 * 1024 * 1024) throw new Error('文本内容不能超过 2 MiB。');
  await addDocument({name, content});
  $('paste-content').value = '';
  $('paste-name').value = '';
}, $('add-text')));
$('search').addEventListener('click', () => action(async () => {
  const query = $('search-query').value.trim();
  if (!query) throw new Error('请输入搜索内容。');
  const ticket = epoch;
  const pid = state.project_id;
  const result = await api(projectPath() + '/search?q=' + encodeURIComponent(query));
  if (ticket !== epoch || pid !== state.project_id) return;
  fillList($('search-results'), result.hits, hit => {
    const node = listRow();
    node.append(el('strong', `${hit.name} · L${hit.line_start}–${hit.line_end}`), el('small', hit.text));
    return node;
  }, '没有找到相关资料。');
}, $('search')));

async function loadSkills() {
  const result = await api('/api/skills');
  fillList($('skill-list'), result.skills, skill => {
    const node = listRow();
    node.append(el('strong', skill.name || skill.ref), el('small', skill.description));
    node.append(el('code', skill.path + '\n' + skill.sha256));
    const actions = el('div', undefined, 'row-actions');
    actions.append(makeButton('只读查看', async () => {
      const parts = skill.ref.replace(/^skill:\/\//, '').split(/[/:]/).filter(Boolean);
      if (parts.length !== 2) throw new Error('Skill 引用格式无法识别：' + skill.ref);
      const view = await api('/api/skills/' + parts.map(encodeURIComponent).join('/'));
      modal(view.ref, [el('code', view.path + '\n' + view.sha256), el('pre', view.content)]);
    }));
    node.append(actions);
    return node;
  }, '暂无可用的本地 Skills。');
}
$('model-form').addEventListener('submit', event => {
  event.preventDefault();
  action(async () => {
    try {
      await api('/api/settings/model', {
        method: 'POST',
        body: JSON.stringify({
          base_url: $('base-url').value.trim(),
          model: $('model').value.trim(),
          api_key: $('api-key').value,
        }),
      });
      await refresh(state.project_id);
      notice('配置已保存至服务会话内存，请测试连接。');
    } finally {
      $('api-key').value = '';
    }
  }, event.submitter);
});
$('test-model').addEventListener('click', () => action(async () => {
  const result = await api('/api/settings/model/test', {method: 'POST', body: '{}'});
  notice(result.message || (result.ok ? '连接测试成功。' : '连接测试失败。'), !result.ok);
}, $('test-model')));
window.addEventListener('beforeunload', event => {
  if (dirty()) {
    event.preventDefault();
    event.returnValue = '';
  }
});

$('notice-close').addEventListener('click', () => {
  clearTimeout(noticeTimer);
  $('notice').hidden = true;
});
$('copy-hash').addEventListener('click', () => action(async () => {
  if (!selected) throw new Error('请先选择任务。');
  if (!await copyText(selected.sha256)) throw new Error('复制失败，请手动选择指纹复制。');
  notice('规格指纹已复制到剪贴板。');
}, $('copy-hash')));
$('modal').addEventListener('keydown', event => {
  if (event.key !== 'Enter' || !event.target.matches('input')) return;
  const primary = $('modal-actions').querySelector('.primary');
  if (primary) {
    event.preventDefault();
    primary.click();
  }
});
$('requirement').addEventListener('keydown', event => {
  if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
    event.preventDefault();
    if (!$('generate').disabled) $('generate').click();
  }
});
$('search-query').addEventListener('keydown', event => {
  if (event.key === 'Enter') {
    event.preventDefault();
    $('search').click();
  }
});
const uploadZone = document.querySelector('.upload-zone');
if (uploadZone) {
  ['dragenter', 'dragover'].forEach(type => uploadZone.addEventListener(type, event => {
    event.preventDefault();
    uploadZone.classList.add('drop-active');
  }));
  ['dragleave', 'drop'].forEach(type => uploadZone.addEventListener(type, event => {
    event.preventDefault();
    uploadZone.classList.remove('drop-active');
  }));
  uploadZone.addEventListener('drop', event => {
    const file = event.dataTransfer.files[0];
    if (!file) return;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    $('file').files = transfer.files;
    $('file-name').textContent = file.name;
  });
}
$('drawer-toggle').addEventListener('click', () => {
  const open = !document.body.classList.contains('drawer-open');
  document.body.classList.toggle('drawer-open', open);
  $('scrim').hidden = !open;
  $('drawer-toggle').setAttribute('aria-expanded', String(open));
  if (open) $('task-search').focus();
});
$('scrim').addEventListener('click', closeDrawer);
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && document.body.classList.contains('drawer-open')) {
    closeDrawer();
    $('drawer-toggle').focus();
  }
});
document.querySelectorAll('[data-page]').forEach(button => button.addEventListener('click', () => {
  if (!allowLeave()) return;
  setPage(button.dataset.page);
  closeDrawer();
  if (button.dataset.page === 'skills') action(loadSkills);
}));
document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => setView(button.dataset.view)));
$('task-search').addEventListener('input', renderTasks);
$('expand-all').addEventListener('change', () => {
  for (const record of execution?.records || []) {
    recordExpansion.set((selected?.id || '') + ':' + record.id, $('expand-all').checked);
  }
  document.querySelectorAll('.record').forEach(details => { details.open = $('expand-all').checked; });
});
$('record-filter').addEventListener('change', renderExecution);
$('locate-error').addEventListener('click', () => {
  const first = $('execution-records').querySelector('.record.error');
  if (!first) return;
  first.open = true;
  first.scrollIntoView({block: 'center', behavior: 'smooth'});
});
$('attachment').addEventListener('click', () => {
  setPage('documents');
  closeDrawer();
});
$('new-task').addEventListener('click', () => {
  if (!allowLeave()) return;
  epoch++;
  clearTimeout(pollTimer);
  executionEpoch++;
  selected = null;
  execution = null;
  $('spec-content').value = '';
  $('spec-title').value = '';
  $('requirement').value = '';
  updateUrl();
  renderSpec();
  renderTasks();
  renderTaskHeader();
  renderExecution();
  $('execution-records').scrollTop = 0;
  syncButtons();
  setPage('workspace');
  setView('execution');
  $('requirement').focus();
});
$('artifacts').addEventListener('click', () => {
  const nodes = (execution?.artifacts || []).map(artifact => {
    const section = el('section');
    section.append(el('h2', artifact.name), el('code', (artifact.path || '') + '\n' + (artifact.sha256 || '')), el('pre', artifact.content));
    return section;
  });
  modal('任务产物与证据', nodes.length ? nodes : [el('p', '当前任务暂无产物。')]);
});

window.refresh = refresh;
Object.defineProperty(window, 'docloopState', {get: () => state});
Object.defineProperty(window, 'state', {get: () => state});
setView(activeView);
action(() => refresh(new URL(location.href).searchParams.get('project_id')));
