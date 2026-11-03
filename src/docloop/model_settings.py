"""本地模型档案；只存Codex登录引用，DeepSeek密钥用当前Windows用户DPAPI保护。"""
import base64
import copy
import ctypes
import json
import os
from pathlib import Path
from threading import RLock
from uuid import uuid4

MODELS = {
    'gpt-6.1-sol': {'label': 'GPT 6.1 Sol', 'provider': 'codex-cli', 'api_model': 'gpt-6.1-sol'},
    'deepseek-v4.1-flash': {'label': 'DeepSeek V4.1 Flash', 'provider': 'chat-completions', 'api_model': 'deepseek-flash'},
}


def protect_secret(raw, *, decrypt=False):
    if os.name != 'nt':
        raise ValueError('此版本的持久密钥存储需要Windows DPAPI；不会保存明文密钥。')
    class Blob(ctypes.Structure):
        _fields_ = [('size', ctypes.c_ulong), ('data', ctypes.c_void_p)]
    buffer = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buffer, ctypes.c_void_p))
    target = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(Blob)]
    function.restype = ctypes.c_int
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ValueError('无法保护或读取模型密钥，请使用保存配置的Windows账户重新配置。')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        if target.data:
            ctypes.memset(target.data, 0, target.size)
            kernel.LocalFree(target.data)


class ModelSettings:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = RLock()
        self.data = {'version': 1, 'selected': 'gpt-6.1-sol', 'profiles': {
            name: {'enabled': False, 'base_url': 'https://api.deepseek.com' if name.startswith('deepseek') else '',
                   'encrypted_key': ''} for name in MODELS}}
        if self.path.exists():
            try:
                if self.path.stat().st_size > 65536:
                    raise ValueError('oversized')
                loaded = json.loads(self.path.read_text(encoding='utf-8'))
                if (loaded.get('version') != 1 or loaded.get('selected') not in MODELS or
                        set(loaded.get('profiles', {})) != set(MODELS)):
                    raise ValueError('invalid schema')
                for profile in loaded['profiles'].values():
                    if (not isinstance(profile.get('enabled'), bool) or
                            not isinstance(profile.get('base_url'), str) or
                            not isinstance(profile.get('encrypted_key'), str)):
                        raise ValueError('invalid profile')
                self.data = loaded
            except (OSError, ValueError, TypeError, AttributeError):
                raise ValueError('模型配置文件无法读取；请检查独立数据目录的.settings/model-settings.json，不会覆盖原文件。') from None

    def _save(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + '.' + uuid4().hex + '.tmp')
        try:
            with temporary.open('x', encoding='utf-8') as stream:
                os.chmod(temporary, 0o600)
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
        self.data = value

    @staticmethod
    def validate(model):
        if model not in MODELS:
            raise ValueError('仅支持GPT 6.1 Sol和DeepSeek V4.1 Flash。')

    def configure(self, model, base_url, api_key):
        self.validate(model)
        with self.lock:
            value = copy.deepcopy(self.data)
            profile = value['profiles'][model]
            if model == 'gpt-6.1-sol':
                if api_key.strip():
                    raise ValueError('GPT使用本机Codex登录，不接收或复制API Key。')
                profile.update(base_url='', encrypted_key='')
            else:
                profile['base_url'] = base_url
                if api_key.strip():
                    profile['encrypted_key'] = base64.b64encode(protect_secret(api_key.strip().encode())).decode('ascii')
                if not profile['encrypted_key']:
                    raise ValueError('首次配置DeepSeek需要API Key。')
            profile['enabled'] = True
            value['selected'] = model
            self._save(value)

    def select(self, model):
        self.validate(model)
        with self.lock:
            value = copy.deepcopy(self.data)
            value['selected'] = model
            self._save(value)

    def public(self, codex_available=False):
        with self.lock:
            model = self.data['selected']
            profile = self.data['profiles'][model]
            return {'model': model, **MODELS[model], 'base_url': profile['base_url'],
                'configured': profile['enabled'] and (codex_available if model == 'gpt-6.1-sol' else bool(profile['encrypted_key'])),
                'has_api_key': bool(profile['encrypted_key']), 'saved': profile['enabled'],
                'credentials_storage': 'codex-login-reference' if model == 'gpt-6.1-sol' else 'windows-dpapi',
                'configuration_storage': 'local-persistent',
                'options': [{'id': key, **info} for key, info in MODELS.items()]}

    def active(self):
        with self.lock:
            model = self.data['selected']
            profile = self.data['profiles'][model]
            key = ''
            if profile['encrypted_key']:
                try:
                    key = protect_secret(base64.b64decode(profile['encrypted_key'], validate=True), decrypt=True).decode('utf-8')
                except (ValueError, UnicodeError):
                    raise ValueError('保存的模型密钥无法读取，请重新配置。') from None
            return {'model': model, **MODELS[model], 'enabled': profile['enabled'],
                    'base_url': profile['base_url'], 'api_key': key}
