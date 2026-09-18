import sys
import unittest
import os
from pathlib import Path
from types import SimpleNamespace
from threading import Thread
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from app.services.explanation_service import (
    AISettingService,
    _classify_ai_error,
    _fernet,
    _openai_stream,
    stream_explanation,
)
from mock_openai_server import serve


class FakeDb:
    def __init__(self, setting=None):
        self.setting = setting

    def get(self, _model, _user_id):
        return self.setting


class AIServiceTests(unittest.TestCase):
    def setUp(self):
        os.environ["AUTH_SESSION_PEPPER"] = "t" * 40

    def test_unconfigured_service_falls_back_without_blocking(self):
        events = list(stream_explanation(
            FakeDb(),
            SimpleNamespace(id=7),
            {"model_result": {"prediction_label": "normal"}, "sample": {}},
        ))
        self.assertEqual(events[0], ("start", {"status": "开始分析"}))
        self.assertEqual(events[1][0], "error")
        self.assertTrue(any(event == "delta" for event, _ in events))
        self.assertEqual(events[-1], ("done", {"status": "已使用规则模板完成", "source": "fallback"}))

    def test_empty_ai_stream_is_classified_and_falls_back(self):
        setting = SimpleNamespace(enabled=True, model="mock-model")
        with patch("app.services.explanation_service._openai_stream", return_value=[]):
            events = list(stream_explanation(
                FakeDb(setting),
                SimpleNamespace(id=7),
                {"model_result": {"prediction_label": "normal"}, "sample": {}},
            ))
        self.assertEqual(events[1][0], "error")
        self.assertEqual(events[1][1]["reason_code"], "provider_error")
        self.assertEqual(events[-1][1]["source"], "fallback")

    def test_provider_error_messages_do_not_echo_exception_content(self):
        code, message = _classify_ai_error(RuntimeError("api_key=secret prompt=private"))
        self.assertEqual(code, "provider_error")
        self.assertNotIn("secret", message)
        self.assertNotIn("private", message)

    def test_local_openai_compatible_mock_supports_real_sdk_stream(self):
        server = serve(port=0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            encrypted = _fernet().encrypt(b"local-test-key").decode("utf-8")
            setting = SimpleNamespace(
                api_key_encrypted=encrypted,
                base_url=f"http://127.0.0.1:{port}/v1",
                model="mock-model",
            )
            chunks = list(_openai_stream(setting, [{"role": "user", "content": "OK"}]))
            self.assertTrue(chunks)
            self.assertIn("Mock 服务", "".join(chunks))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_local_mock_failure_modes_reach_stable_fallback_codes(self):
        expected_codes = {
            "rate_limited": "rate_limited",
            "authentication_failed": "authentication_failed",
            "model_not_found": "model_not_found",
        }
        for mode, expected_code in expected_codes.items():
            server = serve(port=0, mode=mode)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]
                setting = SimpleNamespace(
                    enabled=True,
                    model="mock-model",
                    api_key_encrypted=_fernet().encrypt(b"local-test-key").decode("utf-8"),
                    base_url=f"http://127.0.0.1:{port}/v1",
                )
                events = list(stream_explanation(
                    FakeDb(setting),
                    SimpleNamespace(id=7),
                    {"model_result": {"prediction_label": "normal"}, "sample": {}},
                ))
                error = next(data for event, data in events if event == "error")
                self.assertEqual(error["reason_code"], expected_code)
                self.assertEqual(events[-1][1]["source"], "fallback")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
