from app.config import Settings
from app.llm.base import LLMClient, LLMError, Message
from app.llm.fake import FakeLLMClient
from app.llm.openai_compatible import OpenAICompatibleClient

__all__ = ["LLMClient", "LLMError", "Message", "build_llm"]


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider == "fake":
        return FakeLLMClient()
    return OpenAICompatibleClient(
        settings.llm_base_url,
        settings.llm_api_key.get_secret_value(),
        timeout_s=settings.llm_timeout_s,
    )
