from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from xhs_note_manager.llm import LLMError, OpenAICompatibleClient


class StubHandler(BaseHTTPRequestHandler):
    status = 200
    response_body = b'{}'
    last_path = ""
    last_headers: dict[str, str] = {}
    last_payload: dict = {}

    def do_POST(self) -> None:
        type(self).last_path = self.path
        type(self).last_headers = dict(self.headers.items())
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        type(self).last_payload = json.loads(raw.decode("utf-8"))
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(type(self).response_body)

    def log_message(self, format: str, *args: object) -> None:
        return


class LLMClientTests(unittest.TestCase):
    def setUp(self) -> None:
        StubHandler.status = 200
        StubHandler.response_body = json.dumps({
            "choices": [{"message": {"content": "{\"ok\": true}"}}]
        }).encode("utf-8")
        StubHandler.last_path = ""
        StubHandler.last_headers = {}
        StubHandler.last_payload = {}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}/v1"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_local_endpoint_without_key(self) -> None:
        client = OpenAICompatibleClient(api_key="", base_url=self.base_url, model="stub")
        result = client.complete(system="system", user="user")
        self.assertEqual(result, '{"ok": true}')
        self.assertEqual(StubHandler.last_path, "/v1/chat/completions")
        self.assertNotIn("Authorization", StubHandler.last_headers)
        self.assertEqual(StubHandler.last_payload["model"], "stub")
        self.assertEqual(StubHandler.last_payload["messages"][1]["content"], "user")

    def test_api_key_sent_only_as_bearer_header(self) -> None:
        client = OpenAICompatibleClient(api_key="test-secret", base_url=self.base_url, model="stub")
        client.complete(system="system", user="user")
        self.assertEqual(StubHandler.last_headers["Authorization"], "Bearer test-secret")
        self.assertNotIn("test-secret", json.dumps(StubHandler.last_payload))

    def test_http_and_invalid_json_errors(self) -> None:
        StubHandler.status = 429
        StubHandler.response_body = b'{"error":"rate limited"}'
        with self.assertRaisesRegex(LLMError, "HTTP 429"):
            OpenAICompatibleClient(api_key="", base_url=self.base_url, model="stub").complete(system="s", user="u")

        StubHandler.status = 200
        StubHandler.response_body = b"not-json"
        with self.assertRaisesRegex(LLMError, "有效 UTF-8 JSON"):
            OpenAICompatibleClient(api_key="", base_url=self.base_url, model="stub").complete(system="s", user="u")

    def test_rejects_insecure_remote_http(self) -> None:
        with self.assertRaisesRegex(LLMError, "必须使用 HTTPS"):
            OpenAICompatibleClient(api_key="secret", base_url="http://example.com/v1", model="stub")
        with self.assertRaisesRegex(LLMError, "查询参数"):
            OpenAICompatibleClient(api_key="secret", base_url="https://example.com/v1?api_key=secret", model="stub")


if __name__ == "__main__":
    unittest.main()
