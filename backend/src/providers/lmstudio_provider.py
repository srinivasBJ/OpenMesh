from __future__ import annotations

from .local_openai_compatible import LocalOpenAICompatibleProvider


class LMStudioProvider(LocalOpenAICompatibleProvider):
    provider_id = "lmstudio"
    display_name = "LM Studio"
    env_var = "LMSTUDIO_BASE_URL"
    default_model = "local-model"
    default_endpoint = "http://localhost:1234"
