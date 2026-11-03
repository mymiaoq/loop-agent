"""双模型网关；工作台使用本地持久档案，独立fixture仍可注入通用接口。"""
from threading import RLock, Event
from urllib.parse import urlsplit
import httpx
from .reliability import Reliability, Limits, Blocked
import asyncio
from contextlib import suppress


class ModelUnavailable(RuntimeError):
    pass


class ModelGateway:
    def __init__(self, *, transport=None, settings_path=None, codex_runtime=None):
        self._settings = None
        self._lock = RLock()
        self.transport = transport
        from .model_settings import ModelSettings
        self.store = ModelSettings(settings_path) if settings_path is not None else None
        self.codex_runtime = codex_runtime
        self._active = set()

    def cancel_all(self):
        """服务退出时取消自身持有的只读模型调用，不影响外部Codex会话。"""
        with self._lock:
            for signal in self._active:
                signal.set()
            return len(self._active)

    def _codex(self):
        if self.codex_runtime is None:
            from .codex_runtime import CodexRuntime
            self.codex_runtime = CodexRuntime()
        return self.codex_runtime

    def select(self, model):
        if self.store is None:
            raise ValueError('未启用模型持久化档案。')
        self.store.select(model)
        return self.public_config()

    def configure(self, base_url, model, api_key):
        if self.store is not None and model == 'gpt-6.1-sol':
            self.store.configure(model, '', api_key)
            return self.public_config()
        parts = urlsplit(base_url.strip())
        if (parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username
                or parts.password or parts.query or parts.fragment):
            raise ValueError('模型地址需要有效的HTTP(S)接口基础地址，不含URL凭据或查询参数。')
        if not model.strip() or len(model) > 200 or len(api_key) > 4096:
            raise ValueError('请输入有效模型名称和密钥。')
        if self.store is not None:
            self.store.configure(model, base_url.strip().rstrip('/'), api_key)
            return self.public_config()
        with self._lock:
            self._settings = (base_url.strip().rstrip('/'), model.strip(), api_key.strip())
        return self.public_config()

    def public_config(self):
        if self.store is not None:
            try:
                self._codex()
                available = True
            except RuntimeError:
                available = False
            return self.store.public(available)
        with self._lock:
            settings = self._settings
        return {'configured': settings is not None, 'base_url': settings[0] if settings else '',
                'model': settings[1] if settings else '', 'credentials_storage': 'process-memory-only'}

    def complete(self, messages, *, cancel_event=None):
        signal = cancel_event if cancel_event is not None else Event()
        with self._lock:
            self._active.add(signal)
        try:
            return self._complete(messages, signal)
        finally:
            with self._lock:
                self._active.discard(signal)

    async def _request(self, base, model, key, messages, signal):
        async def invoke():
            async with httpx.AsyncClient(transport=self.transport, timeout=35, follow_redirects=False) as client:
                async with client.stream('POST', base + '/chat/completions', headers={
                        'Authorization': 'Bearer ' + key} if key else {}, json={
                        'model': model, 'messages': messages, 'stream': False, 'max_tokens': 4096}) as response:
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 2 * 1024 * 1024:
                            raise ModelUnavailable('模型响应过大，已停止处理。')
                    return httpx.Response(response.status_code, content=bytes(content))
        task = asyncio.create_task(asyncio.wait_for(invoke(), timeout=35))
        try:
            while not task.done():
                if signal.is_set():
                    raise ModelUnavailable('模型调用已取消。')
                await asyncio.wait({task}, timeout=.05)
            return await task
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    def _complete(self, messages, signal):
        if signal.is_set():
            raise ModelUnavailable('模型调用已取消。')
        if self.store is not None:
            profile = self.store.active()
            if not profile['enabled']:
                raise ModelUnavailable('当前模型尚未配置，请在设置中保存连接。')
            if profile['provider'] == 'codex-cli':
                try:
                    return self._codex().complete(messages, cancel_event=signal)
                except RuntimeError:
                    raise ModelUnavailable('GPT调用未完成。请检查本机Codex登录、该模型权限、取消或超时状态；如果持续出现 405/Method Not Allowed，请重新登录Codex，或切换演示规格。') from None
            settings = (profile['base_url'], profile['api_model'], profile['api_key'])
        else:
            with self._lock:
                settings = self._settings
        if settings is None:
            raise ModelUnavailable('尚未配置真实模型接口；请选择沙箱演示或在设置中连接模型。')
        base, model, key = settings
        reliability = Reliability(Limits(llm=4, model_rounds=4, task_seconds=120, run_seconds=120), sleep=signal.wait)

        def operation():
            if signal.is_set():
                raise ModelUnavailable('模型调用已取消。')
            reliability.charge('llm')
            reliability.charge('model_rounds')
            try:
                response = asyncio.run(self._request(base, model, key, messages, signal))
            except httpx.TimeoutException:
                raise TimeoutError('model request timed out') from None
            except httpx.TransportError:
                raise ConnectionError('model network unavailable') from None
            if signal.is_set():
                raise ModelUnavailable('模型调用已取消。')
            if response.status_code == 429 or response.status_code >= 500:
                raise ConnectionError('model provider temporarily unavailable')
            if response.status_code == 405:
                raise ModelUnavailable('模型接口返回HTTP 405（Method Not Allowed）。请确认 Base URL 是兼容 Chat Completions 的接口根地址（例如 https://api.deepseek.com），不要填写网页地址或工作台地址。')
            if response.status_code != 200:
                raise ModelUnavailable(f'模型接口返回HTTP {response.status_code}，请检查地址、模型名称和凭据。')
            if len(response.content) > 2 * 1024 * 1024:
                raise ModelUnavailable('模型响应过大，已停止处理。')
            try:
                data = response.json()
                content = data['choices'][0]['message']['content']
                if not isinstance(content, str) or not content.strip():
                    raise ValueError('empty')
                usage = data.get('usage') or {}
                if isinstance(usage.get('total_tokens'), int) and usage['total_tokens'] >= 0:
                    reliability.charge('tokens', usage['total_tokens'])
                return {'content': content, 'usage': usage, 'model': model, 'model_invoked': True}
            except (ValueError, KeyError, IndexError, TypeError):
                raise ModelUnavailable('模型响应不是预期的Chat-Completions格式。') from None

        try:
            return reliability.call(operation, external=True)
        except Blocked:
            raise ModelUnavailable('模型调用达到重试或预算上限，请检查连接后重试。') from None

    def test(self):
        self.complete([{'role': 'user', 'content': 'Reply briefly with OK. This is a connectivity check.'}])
        return {'ok': True, 'message': '已收到模型接口的有效响应。'}
