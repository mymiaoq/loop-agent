import json
import os
import tempfile
import unittest
from pathlib import Path
from docloop.model_gateway import ModelGateway


class ModelSettingsTests(unittest.TestCase):
    def test_http_model_wait_can_be_cancelled_without_retry(self):
        import asyncio
        import concurrent.futures
        import threading
        import httpx
        from docloop.model_gateway import ModelUnavailable
        entered, stop = threading.Event(), threading.Event()
        calls = []
        async def provider(request):
            calls.append(request)
            entered.set()
            await asyncio.sleep(5)
            return httpx.Response(200, json={'choices': [{'message': {'content': 'late'}}]})
        gateway = ModelGateway(transport=httpx.MockTransport(provider))
        gateway.configure('https://fixture.local', 'fixture', 'dummy')
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            future = pool.submit(gateway.complete, [{'role': 'user', 'content': 'test'}], cancel_event=stop)
            self.assertTrue(entered.wait(2))
            self.assertEqual(gateway.cancel_all(), 1)
            stop.set()
            with self.assertRaises(ModelUnavailable):
                future.result(timeout=1)
        self.assertEqual(len(calls), 1)
    def test_shutdown_cancels_only_owned_codex_call(self):
        import concurrent.futures
        import threading
        from docloop.model_gateway import ModelUnavailable
        started = threading.Event()
        class WaitingRuntime:
            def complete(self, messages, *, cancel_event):
                started.set()
                if not cancel_event.wait(5):
                    raise AssertionError('Owned request was not cancelled')
                raise RuntimeError('cancelled')
        with tempfile.TemporaryDirectory() as tmp:
            gateway = ModelGateway(settings_path=Path(tmp) / 'model.json', codex_runtime=WaitingRuntime())
            gateway.configure('', 'gpt-6.1-sol', '')
            with concurrent.futures.ThreadPoolExecutor(1) as pool:
                future = pool.submit(gateway.complete, [{'role': 'user', 'content': 'test'}])
                self.assertTrue(started.wait(2))
                self.assertEqual(gateway.cancel_all(), 1)
                with self.assertRaises(ModelUnavailable):
                    future.result(timeout=3)
            self.assertEqual(gateway.cancel_all(), 0)
    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI integration')
    def test_two_profiles_persist_without_exposing_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'model-settings.json'
            gateway = ModelGateway(settings_path=path)
            gateway.configure('https://api.deepseek.com', 'deepseek-v4.1-flash', 'private-test-key')
            public = gateway.public_config()
            self.assertTrue(public['configured'])
            self.assertNotIn('private-test-key', path.read_text(encoding='utf-8'))
            self.assertNotIn('private-test-key', json.dumps(public))
            gateway.select('gpt-6.1-sol')
            restored = ModelGateway(settings_path=path)
            self.assertEqual(restored.public_config()['model'], 'gpt-6.1-sol')
            restored.select('deepseek-v4.1-flash')
            restored.configure('https://api.deepseek.com', 'deepseek-v4.1-flash', '')
            self.assertTrue(restored.public_config()['has_api_key'])
            import httpx
            def reloaded_provider(request):
                self.assertEqual(request.headers['Authorization'], 'Bearer private-test-key')
                return httpx.Response(200, json={'choices': [{'message': {'content': 'persisted'}}]})
            restored.transport = httpx.MockTransport(reloaded_provider)
            self.assertEqual(restored.complete([{'role': 'user', 'content': 'reload check'}])['content'], 'persisted')
            self.assertEqual(len(restored.public_config()['options']), 2)
            with self.assertRaises(ValueError):
                restored.select('arbitrary-model')

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI integration')
    def test_deepseek_display_name_maps_to_provider_model(self):
        import httpx
        observed = []
        def provider(request):
            observed.append(json.loads(request.content))
            self.assertEqual(request.headers['Authorization'], 'Bearer private-test-key')
            return httpx.Response(200, json={'choices': [{'message': {'content': 'OK'}}]})
        with tempfile.TemporaryDirectory() as tmp:
            gateway = ModelGateway(settings_path=Path(tmp) / 'model.json', transport=httpx.MockTransport(provider))
            gateway.configure('https://api.deepseek.com', 'deepseek-v4.1-flash', 'private-test-key')
            self.assertEqual(gateway.complete([{'role': 'user', 'content': 'hello'}])['content'], 'OK')
            self.assertEqual(observed[0]['model'], 'deepseek-flash')
