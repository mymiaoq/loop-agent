"""正式产物目录和派生交付文档；不读取模型输入、凭据或检查点。"""
import re
from .governance import sha256
from .workbench_store import NotFound

MAX_DOCUMENT = 2 * 1024 * 1024
MAX_BUNDLE = 8 * 1024 * 1024
TITLES = {'spec.md': '需求规格', 'decisions.md': '决策记录', 'tasks.md': '执行计划',
          'checkList.md': '验收清单', 'evidence.yaml': '验证证据', 'review.yaml': '审查记录',
          'approval.json': '审批凭据', 'sources.json': '来源记录', 'manifest.yaml': '归档清单',
          'verification.txt': '验证日志', 'result.json': '受控结果', 'plan.json': '结构化任务与测试计划',
          'preparation.json': '工作区准备记录', 'run-summary.json': '准备运行结论',
          'difference-report.json': '补充资料差异与影响报告'}


def catalog(store, project_id, spec_id):
    spec = store.spec(project_id, spec_id)
    runs = store.task_runs(project_id, spec_id, limit=None)
    documents = [{'id': 'spec', 'name': 'spec.md', 'title': '当前需求规格',
                  'run_id': None, 'path': f'database-spec:{spec_id}:revision:{spec["revision"]}',
                  'category': '当前规格', 'size': len(spec['content'].encode('utf-8')), 'available': True}]
    warnings = []
    for run in runs:
        before = len(documents)
        base = store.root / 'runs' / run['id']
        regions = [base / '.docloop/changes' / run['id'], base / '文档/变更记录' / run['id']]
        files = []
        for region in regions:
            if region.resolve() != region.absolute():
                warnings.append(f'{run["id"]}：产物目录包含链接，未读取。')
                continue
            if region.is_dir():
                files.extend(p for p in region.rglob('*') if p.is_file())
        files.extend([base / '.docloop/sessions' / run['id'] / 'result.json',
                      base / '.docloop/recovery' / f'{run["id"]}.json',
                      base / '.docloop/traces' / f'{run["id"]}.jsonl'])
        for file in sorted(set(files)):
            if 'agent-inputs' in file.relative_to(base).parts:
                continue
            if not file.is_file():
                continue
            if file.resolve() != file.absolute() or not file.resolve().is_relative_to(store.root.resolve()):
                warnings.append(f'{run["id"]}/{file.name}：链接或越界文件未读取。')
                continue
            if file.suffix.lower() not in {'.md', '.yaml', '.yml', '.json', '.jsonl', '.txt', '.log'}:
                warnings.append(f'{run["id"]}/{file.name}：当前查看器不支持此格式。')
                continue
            path = file.relative_to(store.root).as_posix()
            try:
                size = file.stat().st_size
            except OSError:
                warnings.append(f'{run["id"]}/{file.name}：文件已变化或无法读取，请刷新。')
                continue
            documents.append({'id': sha256(path.encode())[:24], 'name': file.name,
                'title': TITLES.get(file.name, '恢复记录' if '/recovery/' in path else
                                    '执行轨迹' if '/traces/' in path else file.name),
                'run_id': run['id'], 'path': path, 'size': size, 'available': size <= MAX_DOCUMENT,
                'category': '归档快照' if '/文档/变更记录/' in path else
                            '审批基线' if '/baseline/' in path else
                            '变更材料' if '/changes/' in path else '运行记录',
                'note': '超过2 MiB，需在本地查看。' if size > MAX_DOCUMENT else ''})
        if len(documents) == before:
            warnings.append(f'{run["id"]}：正式产物尚未生成或本地文件已缺失。')
    return {'spec': spec, 'runs': runs, 'documents': documents, 'warnings': warnings}


def overview(data):
    spec = data['spec']
    lines = ['# 任务交付总览', '', spec['title'], '',
             '> 本任务包含演示或执行准备记录；文档汇编不代表真实业务验收，也不代表人工最终验收。', '',
             '## 需求与审批', f'- Spec ID：{spec["id"]}', f'- 修订：{spec["revision"]}',
             f'- 状态：{spec["status"]}', f'- SHA-256：{spec["sha256"]}', '', '## 全部运行']
    if not data['runs']:
        lines.append('尚未运行；执行计划、测试证据及审查材料尚未生成。')
    for run in data['runs']:
        result = run['result'] or {}
        lines.extend([f'### {run["id"]}', f'- 时间：{run["created_at"]}',
                      f'- 类型：{"规划与工作区准备" if run["mode"] == "runtime" else "受控演示"}（{run["mode"]}）',
                      f'- 实际状态：{run["status"]}', f'- Commit：{result.get("commit") or "未产生"}',
                      f'- 归档：{"已记录" if result.get("archive") else "未产生"}'])
        if result.get('error'):
            lines.append(f'- 阻塞/错误：{result["error"]}')
    lines.extend(['', '## 正式文档目录'])
    lines.extend(f'- {d["title"]} · {d["path"]}' + (f' · {d["note"]}' if d.get('note') else '')
                 for d in data['documents'])
    lines.extend(['', '## 范围与缺项',
        '收录当前规格，以及本任务全部历史运行现存的变更文档、审批基线、证据日志、恢复记录、轨迹和归档文件。',
        '计划不等于执行结果。尚未自动生成真实业务技术设计、业务代码和语义变更说明；未生成的材料不会伪造补齐。',
        '此文档按读取时的实际文件动态汇编；运行中的材料可能继续更新，不视为最终交付版本。',
        '模型输入快照、凭据、数据库、Checkpoint和.git内部数据不作为交付文档公开。'])
    lines.extend(data['warnings'])
    return '\n\n'.join(lines)


def read_document(store, data, document):
    if not document['available']:
        raise ValueError(document.get('note') or '文档超过查看上限。')
    if document['id'] == 'spec':
        return data['spec']['content']
    path = store.root / document['path']
    if path.resolve() != path.absolute() or not path.resolve().is_relative_to(store.root.resolve()):
        raise NotFound('产物路径无效。')
    try:
        with path.open('rb') as stream:
            raw = stream.read(MAX_DOCUMENT + 1)
        if len(raw) > MAX_DOCUMENT:
            raise ValueError('文档超过2 MiB，请在本地查看。')
        return raw.decode('utf-8')
    except (OSError, UnicodeError) as error:
        raise ValueError('产物文件已缺失或不是UTF-8文本，请检查本地文件。') from error


def document(store, project_id, spec_id, document_id):
    data = catalog(store, project_id, spec_id)
    origin = f'derived-spec:{spec_id}:revision:{data["spec"]["revision"]}'
    if document_id in {'overview', 'bundle'}:
        content, name = overview(data), '交付总览.md'
        if document_id == 'bundle':
            parts = [content, '\n\n## 原始文档汇编\n']
            size = len(content.encode())
            for item in data['documents']:
                if not item['available']:
                    raise ValueError('存在超限文档，无法汇编全部产物；请逐份查看或在本地处理。')
                text = read_document(store, data, item)
                # 比正文中的连续反引号更长，防止原始内容破坏汇编边界。
                fence = '`' * max(3, 1 + max((len(s) for s in re.findall(r'`+', text)), default=0))
                section = f'\n\n### {item["title"]} · {item["path"]}\n\n{fence}\n{text}\n{fence}\n'
                size += len(section.encode())
                if size > MAX_BUNDLE:
                    raise ValueError('全部产物汇编超过8 MiB，请逐份下载或在本地处理。')
                parts.append(section)
            content, name = ''.join(parts), '全部产物汇编.md'
    else:
        item = next((d for d in data['documents'] if d['id'] == document_id), None)
        if item is None:
            raise NotFound('当前任务中没有此文档。')
        content, name = read_document(store, data, item), item['name']
        origin = item['path']
    return {'id': document_id, 'name': name, 'path': origin, 'content': content,
            'sha256': sha256(content.encode('utf-8'))}
