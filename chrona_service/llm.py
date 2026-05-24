from __future__ import annotations

from chrona_service.config import ChronaConfig
from chrona_service.exceptions import ChronaServiceError
from llm.mock_client import MockLLMClient
from llm_client import DeepSeekLLMClient


def build_llm_client(config: ChronaConfig):
    if config.offline:
        return MockLLMClient()
    if not config.api_key:
        raise ChronaServiceError(
            "DEEPSEEK_API_KEY is not set. Set it in .env or run with --offline for a mock local schedule."
        )
    return DeepSeekLLMClient(
        api_key=config.api_key,
        model=config.model,
        base_url=config.base_url,
    )
