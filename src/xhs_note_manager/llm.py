from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class LLMError(RuntimeError):
    pass


MAX_RESPONSE_BYTES = 2_000_000
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> None:
        return None


class OpenAICompatibleClient:
    def __init__(self, *, api_key: str, base_url: str, model: str, timeout: int = 90):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        parsed = urllib.parse.urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise LLMError("OPENAI_BASE_URL 必须是有效的 http(s) 地址")
        if parsed.username or parsed.password:
            raise LLMError("OPENAI_BASE_URL 不能包含用户名或密码")
        if parsed.query or parsed.fragment:
            raise LLMError("OPENAI_BASE_URL 不能包含查询参数或片段")
        if parsed.scheme == "http" and parsed.hostname not in LOCAL_HOSTS:
            raise LLMError("远程模型地址必须使用 HTTPS；HTTP 仅允许 localhost")
        if not 1 <= timeout <= 600:
            raise LLMError("XHS_MANAGER_TIMEOUT 必须在 1 到 600 秒之间")
        if not model:
            raise LLMError("OPENAI_MODEL 不能为空")
        self._is_local = parsed.hostname in LOCAL_HOSTS
        self._opener = urllib.request.build_opener(NoRedirectHandler())

    def complete(self, *, system: str, user: str) -> str:
        if not self.api_key and not self._is_local:
            raise LLMError("未配置 OPENAI_API_KEY；可先运行 prompt 命令预览提示词。")
        payload = json.dumps({
            "model": self.model,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "xiaohongshu-note-manager/0.1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            method="POST",
            headers=headers,
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise LLMError("模型接口响应超过 2 MB 限制")
                data: dict[str, Any] = json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                exc.read(501)
            finally:
                exc.close()
            raise LLMError(f"模型接口返回 HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise LLMError(f"模型接口连接失败: {exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LLMError("模型接口返回的不是有效 UTF-8 JSON") from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("模型接口响应结构不符合 OpenAI Chat Completions 格式") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMError("模型返回了空内容")
        return content
