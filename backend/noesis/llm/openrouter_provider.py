"""OpenRouter — unified API for 200+ open/closed models.

OpenRouter exposes an OpenAI-compatible wire format, so we extend
:class:`OpenAIProvider` and only swap headers/base-url.
"""

from __future__ import annotations

from noesis.llm.openai_provider import OpenAIProvider
from noesis.types import ProviderType


class OpenRouterProvider(OpenAIProvider):
    provider_id = "openrouter"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        app_name: str = "Noesis",
        site_url: str = "https://github.com/noesis/noesis",
        **kwargs: object,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )
        self._app_name = app_name
        self._site_url = site_url

    # Override headers to include OpenRouter's recommended HTTP headers for
    # rankings / credits.
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._site_url,
            "X-Title": self._app_name,
        }

    # Override provider attribution so ProviderResponse reads as OpenRouter.
    async def _chat_impl(self, *args: object, **kwargs: object) -> object:  # type: ignore[override]
        resp = await super()._chat_impl(*args, **kwargs)  # type: ignore[arg-type]
        resp.provider = ProviderType.OPENROUTER
        return resp
