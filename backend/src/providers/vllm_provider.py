from __future__ import annotations

from .local_openai_compatible import LocalOpenAICompatibleProvider


class VLLMProvider(LocalOpenAICompatibleProvider):
    provider_id = "vllm"
    display_name = "vLLM"
    env_var = "VLLM_BASE_URL"
    default_model = "local-model"
    default_endpoint = "http://localhost:8000"
