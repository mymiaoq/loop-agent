"""可选 Chat-Completions 网关。凭据仅保留本服务进程内存。"""
from threading import RLock
from urllib.parse import urlsplit
import httpx
from .reliability import Reliability, Limits, Blocked


class ModelUnavailable(RuntimeError):
    pass


class ModelGateway:
    def __init__(self, *, transport=None):
        self._settings = None
        self._lock = RLock()
        self.transport = transport

    def configure(self, base_url, model, api_key):
        parts = urlsplit(base_url.strip())
        if (parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username
                or parts.password or parts.query or parts.fragment):
            raise ValueError('模型地址需要有效的HTTP(S)接口基础地址，不含URL凭据或查询参数。')
        if not model.strip() or len(model) > 200 or len(api_key) > 4096:
            raise ValueError('请输入有效模型名称和密钥。')
        with self._lock:
            self._settings = (base_url.strip().rstrip('/'), model.strip(), api_key.strip())
        return self.public_config()

    def public_config(self):
        with self._lock:
            settings = self._settings
        return {'configured': settings is not None, 'base_url': settings[0] if settings else '',
                'model': settings[1] if settings else '', 'credentials_storage': 'process-memory-only'}

    def complete(self, messages):
        with self._lock:
            settings = self._settings
        if settings is None:
            raise ModelUnavailable('尚未配置真实模型接口；请选择沙箱演示或在设置中连接模型。')
        base, model, key = settings
        reliability = Reliability(Limits(llm=4, model_rounds=4, task_seconds=120, run_seconds=120))

        def operation():
            reliability.charge('llm')
            reliability.charge('model_rounds')
            try:
                with httpx.Client(transport=self.transport, timeout=35, follow_redirects=False) as client:
                    response = client.post(base + '/chat/completions', headers={
                        'Authorization': 'Bearer ' + key} if key else {}, json={
                        'model': model, 'messages': messages, 'stream': False, 'max_tokens': 4096})
            except httpx.TimeoutException:
                raise TimeoutError('model request timed out') from None
            except httpx.TransportError:
                raise ConnectionError('model network unavailable') from None
            if response.status_code == 429 or response.status_code >= 500:
                raise ConnectionError('model provider temporarily unavailable')
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
