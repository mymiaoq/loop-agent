"""工作台关系存储；显式 SQLite 沙箱与 Oracle 使用同一数据契约。"""
import hashlib
import heapq
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from sqlalchemy import (Column, ForeignKey, Integer, LargeBinary, MetaData, String, func,
                        Table, Unicode, UnicodeText, UniqueConstraint, create_engine,
                        insert, select, update)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import oracle


class Conflict(ValueError):
    pass


class NotFound(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False)


metadata = MetaData()
projects = Table('dl_project', metadata, Column('id', String(32), primary_key=True),
                 Column('name', Unicode(120), nullable=False), Column('created_at', String(40), nullable=False))
documents = Table('dl_document', metadata, Column('id', String(32), primary_key=True),
    Column('project_id', String(32), ForeignKey('dl_project.id'), nullable=False, index=True),
    Column('name', Unicode(255), nullable=False), Column('version', Integer, nullable=False),
    Column('status', String(20), nullable=False), Column('content_hash', String(64), nullable=False),
    Column('content', UnicodeText, nullable=False), Column('created_at', String(40), nullable=False),
    UniqueConstraint('project_id', 'name', 'version', name='uq_dl_document_revision'))
specs = Table('dl_spec', metadata, Column('id', String(32), primary_key=True),
    Column('project_id', String(32), ForeignKey('dl_project.id'), nullable=False, index=True),
    Column('title', Unicode(200), nullable=False), Column('content', UnicodeText, nullable=False),
    Column('sha256', String(64), nullable=False), Column('revision', Integer, nullable=False),
    Column('status', String(20), nullable=False), Column('generation_mode', String(20), nullable=False),
    Column('references_json', UnicodeText, nullable=False), Column('skill_sources_json', UnicodeText, nullable=False),
    Column('approved_by', Unicode(120)), Column('approval_blob', LargeBinary), Column('approved_hash', String(64)),
    Column('created_at', String(40), nullable=False))
runs = Table('dl_run', metadata, Column('id', String(32), primary_key=True),
    Column('project_id', String(32), ForeignKey('dl_project.id'), nullable=False, index=True),
    Column('spec_id', String(32), ForeignKey('dl_spec.id'), nullable=False), Column('status', String(20), nullable=False),
    Column('mode', String(20), nullable=False), Column('result_json', UnicodeText, nullable=False),
    Column('created_at', String(40), nullable=False))
events = Table('dl_event', metadata, Column('id', String(32), primary_key=True),
    Column('project_id', String(32), ForeignKey('dl_project.id'), nullable=False, index=True),
    Column('kind', String(60), nullable=False), Column('payload_json', UnicodeText, nullable=False),
    Column('created_at', String(40), nullable=False))
requests = Table('dl_request', metadata, Column('id', String(64), primary_key=True),
    Column('project_id', String(32), ForeignKey('dl_project.id'), nullable=False),
    Column('spec_id', String(32), ForeignKey('dl_spec.id'), nullable=False),
    Column('payload_hash', String(64), nullable=False))


class WorkbenchStore:
    def __init__(self, engine, data_root: Path, *, backend='sandbox-sqlite', initialize=False):
        self.engine, self.backend = engine, backend
        self.root = Path(data_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if initialize:
            metadata.create_all(engine)

    @classmethod
    def sandbox(cls, root: Path):
        root = Path(root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        engine = create_engine('sqlite:///' + str(root / 'workbench.sqlite'),
                               connect_args={'check_same_thread': False, 'timeout': 20})
        return cls(engine, root, initialize=True)

    @classmethod
    def oracle(cls, root, *, user, password, dsn, initialize=False):
        if not all((user, password, dsn)):
            raise ValueError('Oracle 配置不完整，未切换到沙箱数据库。')
        import oracledb
        engine = create_engine('oracle+oracledb://',
            creator=lambda: oracledb.connect(user=user, password=password, dsn=dsn), pool_pre_ping=True)
        return cls(engine, root, backend='oracle', initialize=initialize)

    def close(self):
        self.engine.dispose()

    @staticmethod
    def oracle_ddl():
        return '\n\n'.join(str(CreateTable(table).compile(dialect=oracle.dialect())).strip() + ';'
                            for table in metadata.sorted_tables)

    @staticmethod
    def _event(connection, project_id, kind, payload):
        connection.execute(insert(events).values(id=uuid4().hex, project_id=project_id, kind=kind,
                           payload_json=encoded(payload), created_at=now()))

    @staticmethod
    def _project(connection, project_id):
        row = connection.execute(select(projects).where(projects.c.id == project_id)).mappings().first()
        if row is None:
            raise NotFound('项目不存在。')
        return dict(row)

    def create_project(self, name):
        name = name.strip()
        if not name or len(name) > 120:
            raise ValueError('项目名称需为1至120个字符。')
        row = {'id': uuid4().hex, 'name': name, 'created_at': now()}
        with self.engine.begin() as connection:
            connection.execute(insert(projects).values(**row))
            self._event(connection, row['id'], 'project.created', {'name': name})
        return row

    def projects(self):
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(select(projects).order_by(projects.c.created_at)).mappings()]

    def import_document(self, project_id, name, raw):
        if not isinstance(name, str) or any(ch in name for ch in '/\\\x00') or len(name) > 255:
            raise ValueError('资料文件名不合法。')
        if Path(name).suffix.lower() not in {'.md', '.txt'}:
            raise ValueError('本轮支持 UTF-8 编码的 Markdown/TXT。')
        if not raw or len(raw) > 2 * 1024 * 1024:
            raise ValueError('资料不能为空，且不能超过2MiB。')
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError as error:
            raise ValueError('资料不是有效UTF-8文本，请转换编码后导入。') from error
        if not text.strip() or '\x00' in text:
            raise ValueError('资料需要包含有效文本。')
        content_hash = digest(raw)
        with self.engine.begin() as connection:
            self._project(connection, project_id)
            latest_version = select(func.max(documents.c.version)).where(
                documents.c.project_id == project_id, documents.c.name == name).scalar_subquery()
            previous = connection.execute(select(documents.c.version, documents.c.status,
                documents.c.content_hash, documents.c.id, documents.c.project_id,
                documents.c.name, documents.c.created_at).where(
                documents.c.project_id == project_id, documents.c.name == name,
                documents.c.version == latest_version).with_for_update()).mappings().first()
            if previous and previous['status'] == 'active' and previous['content_hash'] == content_hash:
                return {'document': self._document(previous), 'deduplicated': True}
            # 对象先落盘再激活数据库行；失败时至多遗留未引用对象，不发布缺失文件。
            path = self.root / 'objects' / content_hash[:2] / content_hash
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with path.open('xb') as stream:
                    stream.write(raw)
            except FileExistsError:
                if digest(path.read_bytes()) != content_hash:
                    raise Conflict('资料对象校验失败，请检查本地文件库。')
            row = {'id': uuid4().hex, 'project_id': project_id, 'name': name,
                   'version': previous['version'] + 1 if previous else 1, 'status': 'active',
                   'content_hash': content_hash, 'content': text, 'created_at': now()}
            connection.execute(update(documents).where(documents.c.project_id == project_id,
                documents.c.name == name, documents.c.status == 'active').values(status='superseded'))
            try:
                connection.execute(insert(documents).values(**row))
            except IntegrityError as error:
                raise Conflict('资料版本已被其他操作更新，请刷新后重试。') from error
            self._event(connection, project_id, 'document.imported', {'document_id': row['id'], 'name': name,
                        'version': row['version'], 'content_hash': content_hash})
        return {'document': self._document(row), 'deduplicated': False}

    @staticmethod
    def _document(row):
        return {key: value for key, value in dict(row).items() if key != 'content'}

    def documents(self, project_id):
        with self.engine.connect() as connection:
            self._project(connection, project_id)
            columns = [column for column in documents.c if column.name != 'content']
            return [self._document(row) for row in connection.execute(select(*columns).where(
                documents.c.project_id == project_id).order_by(documents.c.created_at.desc())).mappings()]

    def deactivate_document(self, project_id, document_id):
        with self.engine.begin() as connection:
            result = connection.execute(update(documents).where(documents.c.project_id == project_id,
                documents.c.id == document_id).values(status='inactive'))
            if result.rowcount != 1:
                raise NotFound('该项目中不存在这份资料。')
            self._event(connection, project_id, 'document.deactivated', {'document_id': document_id})

    def search(self, project_id, query, limit=6):
        if not query.strip():
            return []
        query = query[:1000].lower()
        tokens = set(re.findall(r'[a-z0-9_]+', query))
        for phrase in re.findall(r'[\u4e00-\u9fff]+', query):
            tokens.update(phrase[i:i + 2] for i in range(max(1, len(phrase) - 1)))
        if limit <= 0:
            return []

        def candidates():
            # 每次只保留一份正文，避免资料数和命中片段数放大内存。
            with self.engine.connect() as connection:
                self._project(connection, project_id)
                rows = connection.execute(select(documents).where(
                    documents.c.project_id == project_id,
                    documents.c.status == 'active')).mappings()
                for row in rows:
                    lines = row['content'].splitlines()
                    for start in range(0, len(lines), 12):
                        snippet = '\n'.join(lines[start:start + 16])[:3000]
                        score = sum(snippet.lower().count(token) for token in tokens)
                        if score:
                            yield {'document_id': row['id'], 'name': row['name'], 'version': row['version'],
                                'content_hash': row['content_hash'], 'line_start': start + 1,
                                'line_end': min(start + 16, len(lines)), 'text': snippet, 'score': score}
        return heapq.nlargest(limit, candidates(), key=lambda hit: hit['score'])

    @staticmethod
    def _spec(row):
        value = dict(row)
        value['references'] = json.loads(value.pop('references_json'))
        value['skill_sources'] = json.loads(value.pop('skill_sources_json'))
        value.pop('approval_blob', None)
        return value

    def create_spec(self, project_id, title, content, mode, references, skill_sources):
        if not title.strip() or len(title) > 200 or not re.search(r'\bAC-\d+\b', content) or len(content) > 200000:
            raise ValueError('Spec需要标题、AC验收编号，且内容不能超过200000字符。')
        if mode not in {'sandbox', 'real'}:
            raise ValueError('需求分析模式不合法。')
        row = {'id': uuid4().hex, 'project_id': project_id, 'title': title.strip(), 'content': content,
               'sha256': digest(content.encode()), 'revision': 1, 'status': 'draft', 'generation_mode': mode,
               'references_json': encoded(references), 'skill_sources_json': encoded(skill_sources), 'created_at': now()}
        with self.engine.begin() as connection:
            self._project(connection, project_id)
            connection.execute(insert(specs).values(**row))
            self._event(connection, project_id, 'spec.created', {'spec_id': row['id'], 'mode': mode, 'sha256': row['sha256']})
        return self.spec(project_id, row['id'])

    def analysis_request(self, project_id, key, title, requirement, mode):
        """创建任务身份与请求去重记录在同一事务内，刷新不会创建第二个任务。"""
        if (not key or len(key) > 120 or not title.strip() or len(title) > 200
                or not requirement.strip() or len(requirement) > 12000 or mode not in {'real', 'sandbox'}):
            raise ValueError('任务标题、需求、模式或请求标识无效。')
        identity = digest((project_id + ':' + key).encode())
        payload_hash = digest(encoded([title, requirement, mode]).encode())
        with self.engine.begin() as connection:
            self._project(connection, project_id)
            old = connection.execute(select(requests).where(requests.c.id == identity)).mappings().first()
            if old:
                if old['payload_hash'] != payload_hash:
                    raise Conflict('同一请求标识不能用于不同需求。')
                sid = old['spec_id']
            else:
                sid = uuid4().hex
                content = '# ' + title.strip() + '\n\n分析正在进行，尚未生成可审批规格。\n\nAC-001：等待需求分析。'
                connection.execute(insert(specs).values(id=sid, project_id=project_id, title=title.strip(),
                    content=content, sha256=digest(content.encode()), revision=1, status='draft',
                    generation_mode=mode, references_json='[]', skill_sources_json='[]', created_at=now()))
                connection.execute(insert(requests).values(id=identity, project_id=project_id,
                    spec_id=sid, payload_hash=payload_hash))
                self._event(connection, project_id, 'analysis.requested', {'spec_id': sid})
        return self.spec(project_id, sid)

    def complete_analysis(self, project_id, spec_id, content, references, skills, revision):
        if not re.search(r'\bAC-\d+\b', content) or len(content) > 200000:
            raise ValueError('分析结果缺少验收编号或过长。')
        with self.engine.begin() as connection:
            changed = connection.execute(update(specs).where(specs.c.id == spec_id,
                specs.c.project_id == project_id, specs.c.status == 'draft', specs.c.revision == revision).values(
                content=content, sha256=digest(content.encode()), revision=revision + 1,
                references_json=encoded(references), skill_sources_json=encoded(skills)))
            if changed.rowcount != 1:
                raise Conflict('草稿已变化或审批，分析结果不会覆盖。')
            self._event(connection, project_id, 'spec.created', {'spec_id': spec_id, 'background': True})
        return self.spec(project_id, spec_id)

    def spec(self, project_id, spec_id):
        with self.engine.connect() as connection:
            row = connection.execute(select(specs).where(specs.c.id == spec_id,
                        specs.c.project_id == project_id)).mappings().first()
            if row is None:
                raise NotFound('该项目中不存在这份Spec。')
            return self._spec(row)

    def specs(self, project_id):
        with self.engine.connect() as connection:
            self._project(connection, project_id)
            return [self._spec(row) for row in connection.execute(select(specs).where(
                specs.c.project_id == project_id).order_by(specs.c.created_at.desc())).mappings()]

    def save_spec(self, project_id, spec_id, content, revision):
        if not content.strip() or len(content) > 200000 or not re.search(r'\bAC-\d+\b', content):
            raise ValueError('Spec不能为空，需要AC验收编号，且不能超过200000字符。')
        self.spec(project_id, spec_id)
        value_hash = digest(content.encode())
        with self.engine.begin() as connection:
            self._analysis_finished(connection, project_id, spec_id)
            result = connection.execute(update(specs).where(specs.c.id == spec_id,
                specs.c.project_id == project_id, specs.c.revision == revision, specs.c.status == 'draft').values(
                content=content, sha256=value_hash, revision=revision + 1))
            if result.rowcount != 1:
                raise Conflict('Spec已审批或版本已变化，请刷新后查看。')
            self._event(connection, project_id, 'spec.saved', {'spec_id': spec_id, 'revision': revision + 1, 'sha256': value_hash})
        return self.spec(project_id, spec_id)

    def approve_spec(self, project_id, spec_id, expected_hash, revision, approver):
        if not approver.strip() or len(approver) > 120:
            raise ValueError('请输入审批人，最多120个字符。')
        spec = self.spec(project_id, spec_id)
        if spec['sha256'] != expected_hash:
            raise Conflict('Spec Hash已变化，请审阅当前版本后再审批。')
        with self.engine.begin() as connection:
            self._analysis_finished(connection, project_id, spec_id)
            result = connection.execute(update(specs).where(specs.c.id == spec_id,
                specs.c.project_id == project_id, specs.c.revision == revision,
                specs.c.sha256 == expected_hash, specs.c.status == 'draft').values(
                status='approved', approved_by=approver.strip(), approved_hash=expected_hash,
                approval_blob=spec['content'].encode('utf-8')))
            if result.rowcount != 1:
                raise Conflict('Spec已审批或版本已变化，不能重复覆盖审批。')
            self._event(connection, project_id, 'spec.approved', {'spec_id': spec_id, 'sha256': expected_hash,
                        'revision': revision, 'approver': approver.strip()})
        return self.spec(project_id, spec_id)

    @staticmethod
    def _analysis_finished(connection, project_id, spec_id):
        requested = connection.execute(select(requests.c.id).where(requests.c.project_id == project_id,
            requests.c.spec_id == spec_id)).first()
        if not requested:
            return
        latest = connection.execute(select(runs.c.status).where(runs.c.project_id == project_id,
            runs.c.spec_id == spec_id, runs.c.mode == 'analysis').order_by(runs.c.created_at.desc())).first()
        if latest is None or latest[0] not in {'succeeded', 'cancelled'}:
            raise Conflict('需求分析尚未完成，请继续分析或先取消后手动编辑。')

    def approved_bytes(self, project_id, spec_id):
        with self.engine.connect() as connection:
            row = connection.execute(select(specs).where(specs.c.id == spec_id,
                        specs.c.project_id == project_id)).mappings().first()
            if row is None:
                raise NotFound('Spec不存在。')
            if row['status'] != 'approved' or not row['approval_blob']:
                raise Conflict('Spec尚未审批，不能执行。')
            raw = bytes(row['approval_blob'])
            if (digest(raw) != row['approved_hash'] or row['sha256'] != row['approved_hash']
                    or digest(row['content'].encode('utf-8')) != row['approved_hash']):
                raise Conflict('审批基线校验失败。')
            return raw

    def approval_record(self, project_id, spec_id):
        spec = self.spec(project_id, spec_id)
        with self.engine.connect() as connection:
            for row in connection.execute(select(events).where(events.c.project_id == project_id,
                    events.c.kind == 'spec.approved').order_by(events.c.created_at.desc())).mappings():
                payload = json.loads(row['payload_json'])
                if payload.get('spec_id') == spec_id and payload.get('sha256') == spec['approved_hash']:
                    return {'sha256': spec['approved_hash'], 'approver': spec['approved_by'],
                            'approved_at': row['created_at'], 'version': spec['revision']}
        raise Conflict('审批审计记录缺失，请检查数据完整性。')

    def recover_interrupted_runs(self):
        """服务获得独占数据目录锁后，标记未完成运行，不自动重放外部操作。"""
        with self.engine.begin() as connection:
            pending = list(connection.execute(select(runs).where(runs.c.status == 'in_progress')).mappings())
            for row in pending:
                resumable = row['mode'] in {'runtime', 'analysis'} and (self.root / 'runs' / row['id'] / 'run-input.json').is_file()
                status = 'interrupted' if resumable else 'blocked'
                previous = json.loads(row['result_json'])
                if previous.get('control') == 'cancel' or previous.get('cancel_requested'):
                    status = 'cancelled'
                result = {**previous, 'status': status, 'mode': row['mode'], 'interrupted': True,
                          'reason': '服务中断；可从保存步骤恢复。' if resumable else '检查点缺失，不能安全恢复。',
                          'real_business_acceptance': False}
                connection.execute(update(runs).where(runs.c.id == row['id'],
                    runs.c.status == 'in_progress').values(status=status, result_json=encoded(result)))
                self._event(connection, row['project_id'], 'run.interrupted', {'run_id': row['id'], 'status': status, 'mode': row['mode']})

    def start_run(self, project_id, spec_id, mode='demo'):
        if mode not in {'demo', 'runtime', 'analysis'}:
            raise ValueError('不支持的运行模式。')
        if mode != 'analysis':
            self.approved_bytes(project_id, spec_id)
        else:
            self.spec(project_id, spec_id)
        row = {'id': uuid4().hex, 'project_id': project_id, 'spec_id': spec_id, 'status': 'in_progress',
               'mode': mode, 'result_json': '{}', 'created_at': now()}
        with self.engine.begin() as connection:
            connection.execute(insert(runs).values(**row))
            self._event(connection, project_id, 'run.started', {'run_id': row['id'], 'spec_id': spec_id, 'mode': mode})
        return {**row, 'result': {}}

    def finish_run(self, project_id, run_id, result):
        with self.engine.begin() as connection:
            mode = connection.execute(select(runs.c.mode).where(runs.c.id == run_id,
                runs.c.project_id == project_id)).scalar_one_or_none()
            updated = connection.execute(update(runs).where(runs.c.id == run_id,
                runs.c.project_id == project_id, runs.c.status == 'in_progress').values(
                status=result['status'], result_json=encoded(result)))
            if updated.rowcount != 1:
                raise Conflict('运行状态已变化。')
            self._event(connection, project_id, 'run.finished', {'run_id': run_id, 'status': result['status'], 'mode': mode})

    def run(self, project_id, run_id):
        with self.engine.connect() as connection:
            row = connection.execute(select(runs).where(runs.c.id == run_id,
                runs.c.project_id == project_id)).mappings().first()
        if row is None:
            raise NotFound('该项目中不存在此运行。')
        value = dict(row)
        value['result'] = json.loads(value.pop('result_json'))
        return value

    def request_cancel(self, project_id, run_id):
        row = self.run(project_id, run_id)
        if row['mode'] != 'runtime' or row['status'] != 'in_progress':
            return
        result = {**row['result'], 'cancel_requested': True}
        with self.engine.begin() as connection:
            updated = connection.execute(update(runs).where(runs.c.id == run_id,
                runs.c.project_id == project_id, runs.c.status == 'in_progress').values(result_json=encoded(result)))
            if updated.rowcount:
                self._event(connection, project_id, 'run.cancel_requested',
                    {'run_id': run_id, 'mode': 'runtime', 'status': 'cancel_requested'})

    def transition_run(self, project_id, run_id, expected, status, details):
        """状态比较更新，避免重复控制或迟到结果覆盖新的决定。"""
        row = self.run(project_id, run_id)
        result = {**row['result'], **details, 'status': status}
        with self.engine.begin() as connection:
            changed = connection.execute(update(runs).where(runs.c.id == run_id,
                runs.c.project_id == project_id, runs.c.status.in_(expected),
                runs.c.result_json == encoded(row['result'])).values(status=status, result_json=encoded(result)))
            if changed.rowcount != 1:
                raise Conflict('运行状态已变化，请刷新。')
            self._event(connection, project_id, 'run.' + status,
                {'run_id': run_id, 'spec_id': row['spec_id'], 'status': status, 'mode': row['mode']})
        return self.run(project_id, run_id)

    def document_content(self, project_id, document_id):
        with self.engine.connect() as connection:
            row = connection.execute(select(documents).where(documents.c.id == document_id,
                documents.c.project_id == project_id)).mappings().first()
        if row is None:
            raise NotFound('该项目中没有此资料版本。')
        return dict(row)

    def pending_runs(self, mode):
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(select(runs).where(
                runs.c.mode == mode, runs.c.status == 'in_progress')).mappings()]

    def history(self, project_id, table=runs, limit=100):
        with self.engine.connect() as connection:
            self._project(connection, project_id)
            rows = [dict(row) for row in connection.execute(select(table).where(table.c.project_id == project_id)
                    .order_by(table.c.created_at.desc()).limit(limit)).mappings()]
        for row in rows:
            key = 'result_json' if table is runs else 'payload_json'
            row['result' if table is runs else 'payload'] = json.loads(row.pop(key))
        return rows

    def event_history(self, project_id):
        return self.history(project_id, events)

    def task_runs(self, project_id, spec_id, limit=20):
        self.spec(project_id, spec_id)
        with self.engine.connect() as connection:
            rows = [dict(row) for row in connection.execute(select(runs).where(
                runs.c.project_id == project_id, runs.c.spec_id == spec_id)
                .order_by(runs.c.created_at.desc(), runs.c.id.desc()).limit(limit)).mappings()]
        for row in rows:
            row['result'] = json.loads(row.pop('result_json'))
        return rows

    def task_summaries(self, project_id):
        ranked = select(runs.c.spec_id, runs.c.id, runs.c.status, runs.c.created_at,
            func.row_number().over(partition_by=runs.c.spec_id,
                order_by=[runs.c.created_at.desc(), runs.c.id.desc()]).label('position'))
        ranked = ranked.where(runs.c.project_id == project_id).subquery()
        with self.engine.connect() as connection:
            return {row['spec_id']: dict(row) for row in connection.execute(
                select(ranked).where(ranked.c.position == 1)).mappings()}

    def task_events(self, project_id, spec_id, run_ids):
        self.spec(project_id, spec_id)
        selected = []
        with self.engine.connect() as connection:
            for row in connection.execute(select(events).where(events.c.project_id == project_id)
                    .order_by(events.c.created_at.desc())).mappings():
                payload = json.loads(row['payload_json'])
                if payload.get('spec_id') == spec_id or payload.get('run_id') in run_ids:
                    selected.append({**dict(row), 'payload': payload})
                    if len(selected) == 100:
                        break
        return list(reversed(selected))
