from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from core.exceptions import LLMProviderError
from llm.base import ReplayGuard, load_dotenv_if_present


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com/chat/completions"


class DeepSeekLLMClient(ReplayGuard):
    """DeepSeek chat client using the OpenAI-compatible JSON API."""

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = DEFAULT_DEEPSEEK_BASE_URL,
        timeout_sec: int = 30,
    ) -> None:
        super().__init__()
        if not api_key:
            raise ValueError("DeepSeek API key is required")
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout_sec = timeout_sec

    @classmethod
    def from_env(cls) -> "DeepSeekLLMClient":
        load_dotenv_if_present()
        api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise LLMProviderError(
                "DEEPSEEK_API_KEY is not set. Set it before running the online demo."
            )
        return cls(
            api_key=api_key,
            model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip(),
            base_url=os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL).strip(),
        )

    def generate_json(
        self,
        system_prompt: str,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.guard(system_prompt, payload, idempotency_key)
        response = self._post_json(build_chat_request(self._model, system_prompt, payload))
        return parse_json_message(extract_message_content(response))

    def _post_json(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        request = build_http_request(self._base_url, self._api_key, request_body)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_sec) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMProviderError(f"DeepSeek HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise LLMProviderError(f"DeepSeek network error: {exc.reason}") from exc
        return decode_provider_json(raw)


def build_chat_request(model: str, system_prompt: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }


def build_http_request(
    base_url: str,
    api_key: str,
    request_body: Dict[str, Any],
) -> urllib.request.Request:
    data = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
    return urllib.request.Request(
        base_url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )


def decode_provider_json(raw: str) -> Dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMProviderError("DeepSeek returned non-JSON response") from exc


def extract_message_content(response: Dict[str, Any]) -> str:
    try:
        return str(response["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMProviderError("DeepSeek response missing message content") from exc


def parse_json_message(content: str) -> Dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").removeprefix("json").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMProviderError("DeepSeek message content is not valid JSON") from exc
