'use strict';
const $ = id => document.getElementById(id);
let state = null, selected = null, epoch = 0, busy = 0;
const drafts = new Map();
const titles = {workspace:['工作台','让每一次交付，都有据可循。'],documents:['资料库','集中管理依据，让需求与来源保持关联。'],runs:['运行记录','保留阶段过程，直面失败与阻塞。'],skills:['本地 Skills','查看本地能力定义与实际内容指纹。'],settings:['设置','配置会话连接，明确环境边界。']};
function el(tag, text, cls) { const n = document.createElement(tag); if(text !== undefined) n.textContent = text; if(cls) n.className = cls; return n; }
function notice(message, error = false) { $('notice').textContent = message; $('notice').className = error ? 'error' : ''; $('notice').hidden = !message; }
function empty(target, message) { target.replaceChildren(el('div', message, 'empty')); }
function dirty() { return selected && $('spec-content').value !== selected.content; }
function allowLeave() { if(!dirty()) return true; if(!confirm('当前规格有未保存的修改。确定放弃这些修改吗？')) return false; drafts.delete(selected.id); $('spec-content').value=selected.content; return true; }
function formatTime(value) { const date=new Date(value); return Number.isNaN(date.getTime())?value:new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',dateStyle:'short',timeStyle:'medium'}).format(date); }
async function api(path, options = {}) { const headers = {'Content-Type':'application/json', ...options.headers}; if(options.method && options.method !== 'GET') headers['X-DocLoop-Token'] = state?.csrf_token || ''; const r = await fetch(path,{...options,headers}); let body; try { body = await r.json(); } catch { throw new Error('服务响应无法读取，请稍后重试。'); } if(!r.ok) throw new Error(body.detail || `请求失败（${r.status}）`); return body; }
async function action(fn, button) { if(button?.disabled) return; busy++; if(button) button.disabled = true; syncButtons(); try { await fn(); } catch(e) { const message=e.message || '操作失败，请重试。'; notice(message,true); if($('modal').open){let error=$('modal-error');if(!error){error=el('p',undefined,'error');error.id='modal-error';error.setAttribute('role','alert');$('modal-body').append(error);}error.textContent=message;} } finally { busy--; if(button) button.disabled = false; syncButtons(); } }
function projectPath() { if(!state?.project_id) throw new Error('请先新建或选择一个项目。'); return '/api/projects/' + encodeURIComponent(state.project_id); }
async function refresh(projectId, preferredSpec, silent=false) {
 if(dirty()) drafts.set(selected.id,$('spec-content').value);
 executionEpoch++;
 const ticket=++epoch, previousId=preferredSpec || selected?.id || new URL(location.href).searchParams.get('task_id');
 if(!silent) notice('正在加载任务…');
 const data=await api('/api/state'+(projectId?'?project_id='+encodeURIComponent(projectId):''));
 if(ticket!==epoch)return;
 const oldId=selected?.id;state=data;selected=data.specs.find(s=>s.id===previousId)||data.specs[0]||null;
 if(selected?.id!==oldId)execution=null;
 render(); updateUrl(); if(!silent)notice(''); await loadExecution();
}
function row(title, subtitle) { const n = el('div', undefined, 'row'); n.append(el('strong',title)); if(subtitle) n.append(el('small',subtitle)); return n; }
function fillList(target, values, make, message) { target.replaceChildren(); if(!values?.length) return empty(target,message); values.forEach(v=>target.append(make(v))); }
function render() { $('project').replaceChildren(); state.projects.forEach(p=>{ const o=el('option',p.name);o.value=p.id; $('project').append(o); }); $('project').value=state.project_id || ''; const active=state.documents.filter(d=>d.status==='active');$('doc-count').textContent=String(active.length); fillList($('context-docs'),active,d=>row(d.name,`版本 ${d.version} · 可检索`),'暂无启用的项目资料'); fillList($('document-list'),state.documents,d=>{const n=row(d.name,`版本 ${d.version} · ${d.status} · ${formatTime(d.created_at)}`);n.append(el('code',d.content_hash));const b=el('button','停用资料');b.disabled=d.status!=='active';b.addEventListener('click',()=>{if(confirm(`确定停用“${d.name}”？停用后不再参与检索。`)) action(async()=>{const pid=state.project_id;await api(projectPath()+'/documents/'+encodeURIComponent(d.id),{method:'DELETE'});if(state.project_id===pid) await refresh(pid);},b);});n.append(b);return n;},'资料库为空，添加文件或粘贴文本。');
 renderSpec();renderRuns();
 const m=state.environment.model || {}; const real=$('generation-mode').querySelector('[value="real"]');real.disabled=!m.configured;real.textContent=m.configured?'真实模型生成':'真实模型（未配置）';if(!m.configured)$('generation-mode').value='sandbox';$('base-url').value=m.base_url || '';$('model').value=m.model || '';const info=$('environment-info');info.replaceChildren();[['存储',state.environment.storage_backend],['数据目录',state.environment.data_root],['模型配置',m.configured?'已配置（连接以测试结果为准）':'未配置'],['Oracle',state.environment.oracle?.configured?'已配置（真实环境验收另行记录）':'未配置']].forEach(([k,v])=>info.append(el('dt',k),el('dd',v)));syncButtons();renderTasks();renderTaskHeader(); }
function renderSpec() { $('spec-empty').hidden=!!selected;$('spec-detail').hidden=!selected;$('references').replaceChildren();if(!selected)return empty($('references'),'选择规格后查看引用');$('spec-content').value=drafts.get(selected.id)??selected.content;$('spec-content').readOnly=selected.status==='approved';$('spec-status').textContent=selected.status==='approved'?'已批准':'待审批';$('spec-revision').textContent='修订 '+selected.revision;$('spec-mode').textContent=selected.generation_mode==='real'?'真实模型生成':'沙箱生成';$('spec-hash').textContent=selected.sha256;$('dirty').textContent=dirty()?'· 保留了未保存的本地修改':'';fillList($('references'),selected.references,r=>{const current=state.documents.find(d=>d.id===r.document_id);const n=row(r.name+` · v${r.version} · L${r.line_start}–${r.line_end}`,r.text);n.append(el('code',r.content_hash || ''));n.append(el('small',current?.status==='active'?'引用快照 · 当前可检索':'历史引用快照 · 此版本已不参与当前检索'));return n;},'当前规格暂无引用');fillList($('skill-sources'),selected.skill_sources,s=>row(s.ref,s.path+' · '+s.sha256),'未记录 Skill 来源');syncButtons(); }
function renderRuns() {fillList($('run-list'),state.runs,r=>{const n=row(r.id,`${r.status} · ${r.mode} · ${r.created_at}`);n.append(el('p','沙箱演示 · 非真实业务验收','muted'));const history=el('pre',typeof r.result?.history==='string'?r.result.history:JSON.stringify(r.result?.history || [],null,2));n.append(history);if(r.result?.error)n.append(el('pre',typeof r.result.error==='string'?r.result.error:JSON.stringify(r.result.error,null,2)));if(r.result?.archive){const d=el('details');d.append(el('summary','归档结果'),el('pre',JSON.stringify(r.result.archive,null,2)));n.append(d);}return n;},'暂无运行记录。批准规格后即可运行沙箱验证。');}
function modal(title, nodes, actions = []) { $('modal-title').textContent=title;$('modal-body').replaceChildren(...nodes);$('modal-actions').replaceChildren(...actions);$('modal').showModal(); }
function makeButton(text, handler, primary=false) {const b=el('button',text,primary?'primary':'');b.type='button';b.addEventListener('click',()=>action(()=>handler(b),b));return b;}
const iconPaths={workspace:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',documents:'M5 3h10l4 4v14H5z M14 3v5h5 M8 12h8 M8 16h8',runs:'M4 5h16v15H4z M8 2v6 M16 2v6 M8 12l3 3 5-5',skills:'M8 3H3v5 M16 3h5v5 M3 16v5h5 M21 16v5h-5 M9 9l-3 3 3 3 M15 9l3 3-3 3',settings:'M12 3v3 M12 18v3 M3 12h3 M18 12h3 M6 6l2 2 M16 16l2 2 M6 18l2-2 M16 8l2-2 M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0'};
document.querySelectorAll('[data-page]').forEach(b=>{const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');svg.setAttribute('fill','none');svg.setAttribute('stroke','currentColor');svg.setAttribute('stroke-width','1.5');const path=document.createElementNS('http://www.w3.org/2000/svg','path');path.setAttribute('d',iconPaths[b.dataset.page]);svg.append(path);b.prepend(svg);});
$('project').addEventListener('change',()=>{if(!allowLeave()){ $('project').value=state.project_id;return;}const pid=$('project').value;selected=null;$('search-results').replaceChildren();action(()=>refresh(pid));});
$('refresh').addEventListener('click',()=>action(()=>refresh(state?.project_id),$('refresh')));
$('new-project').addEventListener('click',()=>{if(!allowLeave())return;const name=prompt('新项目名称');if(name?.trim())action(async()=>{const p=await api('/api/projects',{method:'POST',body:JSON.stringify({name:name.trim()})});selected=null;await refresh(p.id);},$('new-project'));});
$('spec-content').addEventListener('input',()=>{if(selected){if(dirty())drafts.set(selected.id,$('spec-content').value);else drafts.delete(selected.id);}$('dirty').textContent=dirty()?'· 尚未保存':'';syncButtons();});
$('generate').addEventListener('click',()=>action(async()=>{if(!allowLeave())return;const requirement=$('requirement').value.trim(),title=$('spec-title').value.trim() || requirement.split('\n')[0].slice(0,80);if(!requirement)throw new Error('请填写新任务需求。');const pid=state.project_id;const s=await api(projectPath()+'/specs',{method:'POST',body:JSON.stringify({title,requirement,mode:$('generation-mode').value})});if(state.project_id===pid){await refresh(pid,s.id);setPage('workspace');setView('spec');closeDrawer();}},$('generate')));
$('save-spec').addEventListener('click',()=>action(async()=>{const pid=state.project_id,sid=selected.id;const saved=await api(projectPath()+'/specs/'+encodeURIComponent(sid),{method:'PUT',body:JSON.stringify({content:$('spec-content').value,revision:selected.revision})});drafts.delete(sid);if(selected?.id===sid){selected=saved;$('spec-content').value=saved.content;}if(state.project_id===pid)await refresh(pid,sid);},$('save-spec')));
$('approve-spec').addEventListener('click',()=>{if(!selected||dirty())return;const spec=selected,pid=state.project_id;const p=el('p','确认批准当前版本后，该规格将锁定。请核对以下 SHA-256：');const hash=el('code',spec.sha256);const label=el('label','审批人');label.htmlFor='approver';const input=el('input');input.id='approver';input.value='本机用户';modal('审批当前规格',[p,hash,label,input],[makeButton('确认批准此指纹',async()=>{const approver=input.value.trim();if(!approver)throw new Error('请填写审批人。');await api('/api/projects/'+encodeURIComponent(pid)+'/specs/'+encodeURIComponent(spec.id)+'/approve',{method:'POST',body:JSON.stringify({sha256:spec.sha256,revision:spec.revision,approver})});$('modal').close();if(state.project_id===pid)await refresh(pid,spec.id);},true)]);});
$('run-spec').addEventListener('click',()=>action(async()=>{setPage('workspace');setView('execution');closeDrawer();const pid=state.project_id,sid=selected.id;runPending=true;loadExecution().catch(e=>notice(e.message,true));try { await api(projectPath()+'/specs/'+encodeURIComponent(sid)+'/runs',{method:'POST',body:JSON.stringify({scenario:$('scenario').value})});} finally {runPending=false;clearTimeout(pollTimer);}if(state.project_id===pid){await refresh(pid,sid);notice('沙箱验证已返回，执行记录与产物已更新。');}},$('run-spec')));
async function addDocument(payload){const pid=state.project_id;const result=await api(projectPath()+'/documents',{method:'POST',body:JSON.stringify(payload)});if(state.project_id===pid){await refresh(pid);notice(result.deduplicated?'已识别相同内容，复用已有资料。':'资料已添加。');}}
$('upload').addEventListener('click',()=>action(async()=>{const f=$('file').files[0];if(!f)throw new Error('请先选择文件。');if(!/\.(md|txt)$/i.test(f.name)||f.size>2*1024*1024)throw new Error('仅支持不超过 2 MiB 的 .md / .txt 文件。');const bytes=new Uint8Array(await f.arrayBuffer());try{new TextDecoder('utf-8',{fatal:true}).decode(bytes);}catch{throw new Error('文件必须采用 UTF-8 编码。');}let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));await addDocument({name:f.name,data_base64:btoa(binary)});$('file').value='';},$('upload')));
$('add-text').addEventListener('click',()=>action(async()=>{const name=$('paste-name').value.trim(),content=$('paste-content').value;if(!/\.(md|txt)$/i.test(name)||!content.trim())throw new Error('请填写 .md / .txt 文件名和文本内容。');if(new TextEncoder().encode(content).length>2*1024*1024)throw new Error('文本内容不能超过 2 MiB。');await addDocument({name,content});$('paste-content').value='';},$('add-text')));
$('search').addEventListener('click',()=>action(async()=>{const q=$('search-query').value.trim();if(!q)throw new Error('请输入搜索内容。');const ticket=epoch,pid=state.project_id;const result=await api(projectPath()+'/search?q='+encodeURIComponent(q));if(ticket!==epoch||pid!==state.project_id)return;fillList($('search-results'),result.hits,h=>row(`${h.name} · L${h.line_start}–${h.line_end}`,h.text),'没有找到相关资料。');},$('search')));
async function loadSkills(){const result=await api('/api/skills');fillList($('skill-list'),result.skills,s=>{const n=row(s.name || s.ref,s.description);n.append(el('code',s.path+'\n'+s.sha256));n.append(makeButton('只读查看',async()=>{const parts=s.ref.replace(/^skill:\/\//,'').split(/[/:]/).filter(Boolean);if(parts.length!==2)throw new Error('Skill 引用格式无法识别：'+s.ref);const v=await api('/api/skills/'+parts.map(encodeURIComponent).join('/'));modal(v.ref,[el('code',v.path+'\n'+v.sha256),el('pre',v.content)]);}));return n;},'暂无可用的本地 Skills。');}
$('model-form').addEventListener('submit',e=>{e.preventDefault();action(async()=>{try{await api('/api/settings/model',{method:'POST',body:JSON.stringify({base_url:$('base-url').value.trim(),model:$('model').value.trim(),api_key:$('api-key').value})});await refresh(state.project_id);notice('配置已保存至服务会话内存，请测试连接。');}finally{$('api-key').value='';}},e.submitter);});
$('test-model').addEventListener('click',()=>action(async()=>{const r=await api('/api/settings/model/test',{method:'POST',body:'{}'});notice(r.message || (r.ok?'连接测试成功。':'连接测试失败。'),!r.ok);},$('test-model')));
window.addEventListener('beforeunload',e=>{if(dirty()){e.preventDefault();e.returnValue='';}});

let execution = null;
let executionEpoch = 0;
let activeView = 'execution';
let pollTimer = null;
let runPending = false;
const recordExpansion = new Map();
const statusNames = {draft:'待审批',approved:'待运行',in_progress:'执行中',accepted:'沙箱通过',blocked:'阻塞',failed:'失败'};
function taskStatus(spec) {
 return state?.task_summaries?.[spec?.id]?.status || spec?.status || 'draft';
}
function updateUrl() {
 const url = new URL(location.href);
 if(state?.project_id) url.searchParams.set('project_id',state.project_id);
 if(selected) url.searchParams.set('task_id',selected.id); else url.searchParams.delete('task_id');
 history.replaceState(null,'',url);
}
function syncButtons() {
 const approved=selected?.status==='approved';$('save-spec').disabled=!selected||approved||busy>0;$('approve-spec').disabled=!selected||approved||dirty()||busy>0;$('run-spec').disabled=!approved||dirty()||busy>0;$('generate').disabled=!state?.project_id||busy>0;$('project').disabled=busy>0;$('new-project').disabled=busy>0;$('spec-content').readOnly=approved||busy>0;$('busy-status').hidden=busy===0;$('main').setAttribute('aria-busy',String(busy>0));
 $('project').disabled = busy > 0;
 $('new-project').disabled = busy > 0;
 $('new-task').disabled = busy > 0;
 document.querySelectorAll('.task-item').forEach(b=>b.disabled=busy>0);
 ['spec-title','requirement','generation-mode'].forEach(id=>$(id).disabled=busy>0);
 $('spec-content').readOnly = busy > 0 || selected?.status === 'approved';
 $('artifacts').disabled = !execution?.artifacts?.length || busy > 0;
}
function renderTaskHeader() {
 const status=selected?taskStatus(selected):null;
 $('task-title').textContent=selected?.title || '请选择任务';
 $('task-title').title=selected?.title || '';
 $('task-status').textContent=statusNames[status] || status || '';
 $('task-status').dataset.status=status || '';
 $('execution-boundary').textContent='受控沙箱验证不代表真实业务验收 · '+(state?.environment.oracle?.configured?'Oracle关系存储已配置':'SQLite沙箱');
 $('bottom-status').textContent=selected?`当前任务 · ${statusNames[status] || status}`:'等待创建或选择任务';
 const latest=state?.task_summaries?.[selected?.id];
 const archived=!!execution?.runs?.find(r=>r.id===latest?.id)?.result?.archive;
 const flags=[!!selected,selected?.status==='approved',latest?.status==='accepted',archived];
 $('stage-count').textContent=flags.filter(Boolean).length+'/4';
 $('stage-list').replaceChildren();
 ['需求规格','版本审批','受控验证','结果归档'].forEach((name,i)=>{
  const n=el('div',undefined,'stage'+(flags[i]?' done':''));
  n.append(el('span',flags[i]?'✓':'○'),el('span',name),el('span',flags[i]?'已完成':'待完成'));
  $('stage-list').append(n);
 });
}
function renderTasks() {
 const previousScroll=$('task-list').scrollTop;
 const q=$('task-search').value.trim().toLowerCase();
 const specs=(state?.specs || []).filter(s=>s.title.toLowerCase().includes(q));
 fillList($('task-list'),specs,s=>{
  const b=el('button',undefined,'task-item'+(s.id===selected?.id?' active':''));
  b.title=s.title;b.setAttribute('aria-current',s.id===selected?.id?'true':'false');
  b.append(el('span',s.title,'task-name'),el('span',statusNames[taskStatus(s)] || taskStatus(s),'task-label'));
  b.dataset.status=taskStatus(s);
  b.disabled=busy>0;
  b.addEventListener('click',()=>{
   if(busy||!allowLeave())return;
   epoch++;clearTimeout(pollTimer);selected=s; execution=null; executionEpoch++;
   renderSpec();renderTasks();renderTaskHeader();renderExecution();updateUrl();setPage('workspace');closeDrawer();
   action(loadExecution);
  });
  return b;
 },q?'未找到匹配任务':'暂无任务，在下方描述需求开始。');
 $('task-list').scrollTop=previousScroll;
}
function setView(view) {
 activeView=view;
 $('execution-view').hidden=view!=='execution';
 $('spec-view').hidden=view!=='spec';
 document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.view===view)));
}
function setPage(page) {
 document.querySelectorAll('.page').forEach(n=>n.hidden=n.id!==page);
 document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page===page));
 $('page-title').textContent=page==='workspace'?'任务执行':titles[page][0];
}
async function loadExecution() {
 clearTimeout(pollTimer);
 const ticket=++executionEpoch,pid=state?.project_id,sid=selected?.id;
 if(!sid){execution=null;empty($('execution-records'),'选择任务后查看实际执行记录。');syncButtons();return;}
 const result=await api('/api/projects/'+encodeURIComponent(pid)+'/specs/'+encodeURIComponent(sid)+'/execution');
 if(ticket!==executionEpoch||pid!==state?.project_id||sid!==selected?.id)return;
 execution=result;renderExecution();renderTaskHeader();syncButtons();
 if(taskStatus(selected)==='in_progress'||runPending){
  schedulePoll(pid,sid);
 }
}
function schedulePoll(pid,sid){
 pollTimer=setTimeout(()=>{
  if(pid!==state?.project_id||sid!==selected?.id)return;
  if(document.hidden){schedulePoll(pid,sid);return;}
  refresh(pid,sid,true).catch(e=>notice(e.message,true));
 },800);
}
function renderExecution() {
 const scrollTop=$('execution-view').scrollTop;
 $('record-scope').textContent=(execution?.record_scope || '最近20次运行')+'；仅显示实际执行记录，不展示模型推理。沙箱结果不代表真实业务验收。';
 const filter=$('record-filter').value;
 const records=(execution?.records||[]).filter(r=>filter==='all'||r.type===filter||(filter==='exception'&&['verification','error'].includes(r.type)));
 fillList($('execution-records'),records,r=>{
  const key=(selected?.id || '')+':'+r.id;
  const d=el('details',undefined,'record'+(r.type==='error'?' error':''));
  d.dataset.recordKey=key;
  d.open=recordExpansion.has(key)?recordExpansion.get(key):$('expand-all').checked;
  d.addEventListener('toggle',()=>recordExpansion.set(key,d.open));
  const summary=el('summary');
  summary.append(el('span',r.title,'record-title'),el('span',r.summary || '', 'record-summary'));
  if(r.result!==undefined && r.result!==null) summary.append(el('span',typeof r.result==='string'?r.result:JSON.stringify(r.result),'record-result'));
  d.append(summary);
  if(r.created_at)d.append(el('small',formatTime(r.created_at)));
  d.append(el('pre',r.detail || '该记录没有更多详情。'));
  if(r.run_id)d.append(el('code','运行：'+r.run_id));
  return d;
 },'当前筛选下暂无执行记录。审批规格后可运行沙箱验证。');
 $('execution-view').scrollTop=scrollTop;
}
function closeDrawer() {
 document.body.classList.remove('drawer-open');$('scrim').hidden=true;
 $('drawer-toggle').setAttribute('aria-expanded','false');
}
$('drawer-toggle').addEventListener('click',()=>{
 const open=!document.body.classList.contains('drawer-open');
 document.body.classList.toggle('drawer-open',open);$('scrim').hidden=!open;
 $('drawer-toggle').setAttribute('aria-expanded',String(open));
 if(open)$('task-search').focus();
});
$('scrim').addEventListener('click',closeDrawer);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&document.body.classList.contains('drawer-open')){closeDrawer();$('drawer-toggle').focus();}});
document.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>{if(!allowLeave())return;setPage(b.dataset.page);closeDrawer();if(b.dataset.page==='skills')action(loadSkills);}));
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>setView(b.dataset.view)));
$('task-search').addEventListener('input',renderTasks);
$('expand-all').addEventListener('change',()=>{for(const record of execution?.records||[])recordExpansion.set((selected?.id||'')+':'+record.id,$('expand-all').checked);document.querySelectorAll('.record').forEach(d=>{d.open=$('expand-all').checked;});});
$('record-filter').addEventListener('change',renderExecution);
$('attachment').addEventListener('click',()=>{setPage('documents');closeDrawer();});
$('new-task').addEventListener('click',()=>{if(!allowLeave())return;epoch++;clearTimeout(pollTimer);executionEpoch++;selected=null;execution=null;$('spec-content').value='';$('spec-title').value='';$('requirement').value='';updateUrl();renderSpec();renderTasks();renderTaskHeader();renderExecution();syncButtons();setPage('workspace');setView('execution');$('requirement').focus();});
$('artifacts').addEventListener('click',()=>{
 const nodes=(execution?.artifacts||[]).map(a=>{const n=el('section');n.append(el('h2',a.name),el('code',(a.path||'')+'\n'+(a.sha256||'')),el('pre',a.content));return n;});
 modal('任务产物与证据',nodes.length?nodes:[el('p','当前任务暂无产物。')]);
});
window.refresh=refresh;
Object.defineProperty(window,'docloopState',{get:()=>state});
Object.defineProperty(window,'state',{get:()=>state});
setView(activeView);
action(()=>refresh(new URL(location.href).searchParams.get('project_id')));
