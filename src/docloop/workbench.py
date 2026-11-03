"""Loopback 工作台：资料、Spec 审批、沙箱运行与本地 Skills。"""
import argparse
import base64
import os
import secrets
import socket
import sys
import threading
import time
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from .model_gateway import ModelUnavailable
from .skill_runtime import SkillRegistry
from .workbench_service import WorkbenchService
from .workbench_store import WorkbenchStore, Conflict, NotFound
from .execution_lock import run_lock
from .governance import GateError
from . import __version__


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ProjectInput(Input):
    name: str = Field(min_length=1, max_length=120)


class DocumentInput(Input):
    name: str = Field(min_length=1, max_length=255)
    content: str | None = Field(default=None, max_length=2097152)
    data_base64: str | None = Field(default=None, max_length=3000000)


class SpecInput(Input):
    title: str = Field(min_length=1, max_length=200)
    requirement: str = Field(min_length=1, max_length=12000)
    mode: str = 'sandbox'


class AnalysisInput(SpecInput):
    request_id: str = Field(min_length=1, max_length=120)


class SupplementInput(DocumentInput):
    mode: str = 'real'


class SpecEdit(Input):
    content: str = Field(min_length=1, max_length=200000)
    revision: int = Field(ge=1)


class Approval(Input):
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    revision: int = Field(ge=1)
    approver: str = Field(min_length=1, max_length=120)


class RunInput(Input):
    scenario: str = 'success'


class ModelInput(Input):
    base_url: str = Field(default='', max_length=2000)
    model: str = Field(max_length=200)
    api_key: str = Field(default='', max_length=4096, repr=False)


class ModelSelection(Input):
    model: str = Field(max_length=200)


class RepositoryInput(Input):
    path: str = Field(min_length=1, max_length=2000)


def create_app(project_root: Path, data_root: Path, *, storage='sandbox', initialize_oracle=False):
    project_root, data_root = Path(project_root).resolve(), Path(data_root).resolve()
    if storage == 'sandbox':
        store = WorkbenchStore.sandbox(data_root)
    elif storage == 'oracle':
        store = WorkbenchStore.oracle(data_root, user=os.getenv('DOCLOOP_ORACLE_USER'),
            password=os.getenv('DOCLOOP_ORACLE_PASSWORD'), dsn=os.getenv('DOCLOOP_ORACLE_DSN'),
            initialize=initialize_oracle)
    else:
        raise ValueError('请选择sandbox或oracle存储模式。')
    service = WorkbenchService(project_root, store)
    token = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app):
        locked = False
        try:
            with run_lock(data_root, 'workbench-service'):
                locked = True
                try:
                    store.recover_interrupted_runs()
                    yield
                finally:
                    try:
                        service.close()
                    finally:
                        store.close()
        finally:
            if not locked:
                store.close()

    app = FastAPI(title='DocLoop Workbench', lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.service = service

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        if request.url.hostname not in {'127.0.0.1', 'localhost', '::1'}:
            return JSONResponse({'detail': '工作台仅接受本机地址。'}, status_code=403)
        if int(request.headers.get('content-length', '0') or '0') > 4 * 1024 * 1024:
            return JSONResponse({'detail': '请求过大。'}, status_code=413)
        if request.method in {'POST', 'PUT', 'DELETE', 'PATCH'}:
            origin = request.headers.get('origin')
            if origin:
                parts = urlsplit(origin)
                if parts.netloc != request.url.netloc or parts.scheme != request.url.scheme:
                    return JSONResponse({'detail': '已拒绝跨来源写入请求。'}, status_code=403)
            supplied = request.headers.get('x-docloop-token', '')
            if not secrets.compare_digest(supplied, token):
                return JSONResponse({'detail': '页面会话已失效，请刷新后重试。'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        return response

    @app.exception_handler(NotFound)
    async def missing(request, error):
        return JSONResponse({'detail': str(error)}, status_code=404)

    @app.exception_handler(Conflict)
    async def conflict(request, error):
        return JSONResponse({'detail': str(error)}, status_code=409)

    @app.exception_handler(ModelUnavailable)
    async def model_error(request, error):
        return JSONResponse({'detail': str(error)}, status_code=502)

    @app.exception_handler(ValueError)
    async def invalid(request, error):
        return JSONResponse({'detail': str(error)}, status_code=400)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, error):
        return JSONResponse({'detail': '参数格式不正确，请检查必填项、长度和版本。'}, status_code=400)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, error):
        return JSONResponse({'detail': '数据库操作未完成，请检查连接和表结构；不会自动切换存储模式。'}, status_code=503)

    @app.get('/api/state')
    def state(project_id: str | None = None):
        return {**service.state(project_id), 'csrf_token': token}

    @app.get('/api/health')
    def health():
        return {'application': 'docloop-workbench', 'version': __version__,
                'project_root': str(project_root), 'data_root': str(data_root), 'storage_backend': store.backend}

    @app.post('/api/shutdown')
    def shutdown():
        callback = getattr(app.state, 'stop_callback', None)
        if callback is None:
            raise Conflict('当前并非独立运行的工作台服务。')
        service.stop_owned_runs()
        callback()
        return {'ok': True, 'message': '已请求停止工作台，正在等待活动请求结束。'}

    @app.post('/api/projects')
    def add_project(body: ProjectInput):
        return store.create_project(body.name)

    @app.post('/api/projects/{project_id}/documents')
    def add_document(project_id: str, body: DocumentInput):
        if (body.content is None) == (body.data_base64 is None):
            raise ValueError('请提交文本或文件内容，不能同时提交两种。')
        raw = body.content.encode('utf-8') if body.content is not None else base64.b64decode(body.data_base64, validate=True)
        return store.import_document(project_id, body.name, raw)

    @app.delete('/api/projects/{project_id}/documents/{document_id}')
    def remove_document(project_id: str, document_id: str):
        store.deactivate_document(project_id, document_id)
        return {'ok': True}

    @app.get('/api/projects/{project_id}/search')
    def search(project_id: str, q: str = ''):
        return {'hits': store.search(project_id, q)}

    @app.post('/api/projects/{project_id}/specs')
    def create_spec(project_id: str, body: SpecInput):
        return service.generate_spec(project_id, body.title, body.requirement, body.mode)

    @app.post('/api/projects/{project_id}/analysis-tasks')
    def analyze_task(project_id: str, body: AnalysisInput):
        return service.start_analysis(project_id, body.title, body.requirement, body.mode, body.request_id)

    @app.post('/api/projects/{project_id}/repository')
    def register_repository(project_id: str, body: RepositoryInput):
        from .execution_preparation import ExecutionPreparation
        return ExecutionPreparation(store).register(project_id, body.path)

    @app.post('/api/projects/{project_id}/specs/{spec_id}/prepare')
    def prepare_execution(project_id: str, spec_id: str):
        from .execution_preparation import ExecutionPreparation
        return ExecutionPreparation(store).prepare(project_id, spec_id)

    @app.post('/api/projects/{project_id}/specs/{spec_id}/runtime-runs')
    def start_runtime(project_id: str, spec_id: str):
        return service.start_runtime(project_id, spec_id)

    @app.get('/api/projects/{project_id}/runtime-runs/{run_id}')
    def runtime_status(project_id: str, run_id: str):
        return store.run(project_id, run_id)

    @app.post('/api/projects/{project_id}/runtime-runs/{run_id}/cancel')
    def cancel_runtime(project_id: str, run_id: str):
        return service.runtime().cancel(project_id, run_id)

    @app.post('/api/projects/{project_id}/runtime-runs/{run_id}/pause')
    def pause_runtime(project_id: str, run_id: str):
        return service.runtime().pause(project_id, run_id)

    @app.post('/api/projects/{project_id}/runtime-runs/{run_id}/resume')
    def resume_runtime(project_id: str, run_id: str):
        return service.runtime().resume(project_id, run_id)

    @app.get('/api/projects/{project_id}/specs/{spec_id}/updates')
    def task_updates(project_id: str, spec_id: str):
        return {'updates': service.updates().list(project_id, spec_id)}

    @app.post('/api/projects/{project_id}/specs/{spec_id}/updates')
    def supplement_task(project_id: str, spec_id: str, body: SupplementInput):
        if (body.content is None) == (body.data_base64 is None):
            raise ValueError('请提交文本或文件内容。')
        raw = body.content.encode('utf-8') if body.content is not None else base64.b64decode(body.data_base64, validate=True)
        return service.updates().submit(project_id, spec_id, body.name, raw, body.mode)

    @app.post('/api/projects/{project_id}/specs/{spec_id}/updates/{update_id}/retry')
    def retry_update(project_id: str, spec_id: str, update_id: str):
        return service.updates().retry(project_id, spec_id, update_id)

    @app.post('/api/projects/{project_id}/specs/{spec_id}/updates/{update_id}/dismiss')
    def dismiss_update(project_id: str, spec_id: str, update_id: str):
        return service.updates().dismiss(project_id, spec_id, update_id)

    def publications():
        from .publications import PublicationService
        return PublicationService(store)

    @app.get('/api/projects/{project_id}/specs/{spec_id}/publications')
    def list_publications(project_id: str, spec_id: str):
        return {'publications': publications().list(project_id, spec_id)}

    @app.post('/api/projects/{project_id}/specs/{spec_id}/publications')
    def publish(project_id: str, spec_id: str):
        return publications().publish(project_id, spec_id)

    @app.post('/api/projects/{project_id}/specs/{spec_id}/publications/{version}/sync')
    def sync_publication(project_id: str, spec_id: str, version: str):
        return publications().sync(project_id, spec_id, version)

    @app.get('/api/projects/{project_id}/specs/{spec_id}/publications/{version}/document')
    def publication_document(project_id: str, spec_id: str, version: str, path: str):
        return publications().document(project_id, spec_id, version, path)

    @app.get('/api/projects/{project_id}/specs/{spec_id}/execution')
    def execution(project_id: str, spec_id: str):
        return service.execution(project_id, spec_id)

    @app.get('/api/projects/{project_id}/specs/{spec_id}/deliverables')
    def deliverables(project_id: str, spec_id: str):
        return service.deliverables(project_id, spec_id)

    @app.get('/api/projects/{project_id}/specs/{spec_id}/deliverables/{document_id}')
    def deliverable(project_id: str, spec_id: str, document_id: str):
        return service.deliverable(project_id, spec_id, document_id)

    @app.put('/api/projects/{project_id}/specs/{spec_id}')
    def edit_spec(project_id: str, spec_id: str, body: SpecEdit):
        return store.save_spec(project_id, spec_id, body.content, body.revision)

    @app.post('/api/projects/{project_id}/specs/{spec_id}/approve')
    def approve_spec(project_id: str, spec_id: str, body: Approval):
        value = store.approve_spec(project_id, spec_id, body.sha256, body.revision, body.approver)
        service.updates().approved(project_id, spec_id)
        return value

    @app.post('/api/projects/{project_id}/specs/{spec_id}/runs')
    def run_spec(project_id: str, spec_id: str, body: RunInput):
        return service.run_demo(project_id, spec_id, body.scenario)

    @app.get('/api/skills')
    def skills():
        return {'skills': service.skills()}

    @app.get('/api/skills/{namespace}/{name}')
    def skill(namespace: str, name: str):
        return SkillRegistry(project_root).load(f'{namespace}:{name}')

    @app.post('/api/settings/model')
    def configure_model(body: ModelInput):
        return service.gateway.configure(body.base_url, body.model, body.api_key)

    @app.post('/api/settings/model/select')
    def select_model(body: ModelSelection):
        return service.gateway.select(body.model)

    @app.post('/api/settings/model/test')
    def test_model():
        return service.gateway.test()

    app.mount('/', StaticFiles(directory=Path(__file__).parent / 'workbench_static', html=True), name='workbench')
    return app


def find_instance(project_root, data_root, port, storage=None, *, require_current_version=True):
    import httpx
    if not port:
        return None
    url = f'http://127.0.0.1:{port}'
    try:
        with httpx.Client(timeout=1, trust_env=False) as client:
            response = client.get(url + '/api/health')
            response.raise_for_status()
            health = response.json()
        expected_backend = {'sandbox': 'sandbox-sqlite', 'oracle': 'oracle'}.get(storage)
        if (isinstance(health, dict) and health.get('application') == 'docloop-workbench'
                and (not require_current_version or health.get('version') == __version__)
                and (expected_backend is None or health.get('storage_backend') == expected_backend)
                and Path(health['project_root']) == Path(project_root).resolve()
                and Path(health['data_root']) == Path(data_root).resolve()):
            return url
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        pass
    return None


def stop_existing(project_root, data_root, port):
    import httpx
    # 升级后的启动器也能停止旧版本，但仍必须匹配项目与数据目录。
    url = find_instance(project_root, data_root, port, require_current_version=False)
    if url is None:
        return {'ok': True, 'message': '未找到此项目与数据目录对应的运行中工作台。'}
    with httpx.Client(timeout=5, trust_env=False) as client:
        session = client.get(url + '/api/state')
        session.raise_for_status()
        result = client.post(url + '/api/shutdown', headers={'X-DocLoop-Token': session.json()['csrf_token']})
        result.raise_for_status()
        answer = result.json()
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            probe.settimeout(.2)
            if probe.connect_ex(('127.0.0.1', port)) != 0:
                try:
                    # Uvicorn先关监听端口，活动请求和lifespan此时可能仍持有数据锁。
                    with run_lock(Path(data_root), 'workbench-service'):
                        return answer
                except GateError:
                    pass
        time.sleep(.1)
    raise ValueError('旧工作台仍在处理请求，尚未释放端口或数据锁；请稍后再次启动。')


def serve(project_root, data_root, *, port=8765, storage='sandbox', open_browser=False, initialize_oracle=False,
          restart=False):
    import uvicorn
    if restart:
        stop_existing(project_root, data_root, port)
    existing = find_instance(project_root, data_root, port, storage) if open_browser else None
    if existing:
        webbrowser.open(existing)
        return
    app = create_app(project_root, data_root, storage=storage, initialize_oracle=initialize_oracle)
    sock = socket.socket()
    try:
        sock.bind(('127.0.0.1', port))
    except OSError:
        raise ValueError('工作台端口已被占用，请关闭旧工作台或选择其他端口。') from None
    actual_port = sock.getsockname()[1]
    url = f'http://127.0.0.1:{actual_port}'
    print(f'DocLoop: {url}\nStorage: {storage}\nData: {data_root}', flush=True)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=actual_port, log_level='warning'))
    app.state.stop_callback = lambda: setattr(server, 'should_exit', True)
    if open_browser:
        def launch():
            for _ in range(100):
                if server.started:
                    webbrowser.open(url)
                    return
                time.sleep(0.1)
        threading.Thread(target=launch, daemon=True).start()
    try:
        server.run(sockets=[sock])
    finally:
        sock.close()


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--data-root', type=Path)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--storage', choices=['sandbox', 'oracle'], default='sandbox')
    parser.add_argument('--open', action='store_true')
    parser.add_argument('--init-db', action='store_true')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--restart', action='store_true')
    args = parser.parse_args()
    data_root = args.data_root or Path(os.environ.get('DOCLOOP_DATA_ROOT', str(args.root.resolve().parent / 'agent-loop-data')))
    if args.stop:
        import json
        print(json.dumps(stop_existing(args.root, data_root, args.port), ensure_ascii=False))
        return
    if args.check:
        app = create_app(args.root, data_root, storage=args.storage, initialize_oracle=args.init_db)
        try:
            app.state.service.state()
            import json
            print(json.dumps(app.state.service.environment(), ensure_ascii=False))
        finally:
            app.state.service.store.close()
        return
    serve(args.root, data_root, port=args.port,
          storage=args.storage, open_browser=args.open, initialize_oracle=args.init_db, restart=args.restart)


if __name__ == '__main__':
    main()
