import json
import unittest
import httpx
from docloop.model_gateway import ModelGateway, ModelUnavailable


class ModelGatewayTests(unittest.TestCase):
    def test_real_request_contains_local_messages_and_never_echoes_key(self):
        observed = []
        def handler(request):
            observed.append(json.loads(request.content))
            self.assertEqual(request.headers['authorization'], 'Bearer test-secret')
            return httpx.Response(200, json={'choices': [{'message': {'content': '# Real\nAC-001: output'}}],
                                            'usage': {'total_tokens': 123}})
        gateway = ModelGateway(transport=httpx.MockTransport(handler))
        gateway.configure('http://fixture.local/v1', 'fixture-model', 'test-secret')
        answer = gateway.complete([{'role': 'system', 'content': 'LOCAL-SKILL'}, {'role': 'user', 'content': 'source'}])
        self.assertIn('AC-001', answer['content'])
        self.assertEqual(observed[0]['messages'][0]['content'], 'LOCAL-SKILL')
        self.assertNotIn('test-secret', json.dumps(gateway.public_config()))
        self.assertEqual(answer['usage']['total_tokens'], 123)

    def test_missing_config_and_provider_error_do_not_fallback_or_leak(self):
        gateway = ModelGateway()
        with self.assertRaises(ModelUnavailable):
            gateway.complete([])
        gateway = ModelGateway(transport=httpx.MockTransport(lambda request:
            httpx.Response(401, text='test-secret invalid password')))
        gateway.configure('http://fixture.local/v1', 'fixture', 'test-secret')
        with self.assertRaises(ModelUnavailable) as caught:
            gateway.complete([{'role': 'user', 'content': 'hi'}])
        self.assertNotIn('test-secret', str(caught.exception))

    def test_method_not_allowed_explains_base_url_without_leaking_key(self):
        gateway = ModelGateway(transport=httpx.MockTransport(lambda request:
            httpx.Response(405, text='Method Not Allowed')))
        gateway.configure('http://fixture.local/v1', 'fixture', 'test-secret')
        with self.assertRaises(ModelUnavailable) as caught:
            gateway.complete([{'role': 'user', 'content': 'hi'}])
        message = str(caught.exception)
        self.assertIn('405', message)
        self.assertIn('Base URL', message)
        self.assertNotIn('test-secret', message)

    def test_endpoint_credentials_and_non_http_are_rejected(self):
        for url in ('file:///secret', 'https://user:password@host/v1', 'https://host/v1?key=secret'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                ModelGateway().configure(url, 'model', 'key')
