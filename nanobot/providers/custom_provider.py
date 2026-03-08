"""Direct OpenAI-compatible provider — bypasses LiteLLM."""

from __future__ import annotations

import uuid
from typing import Any

import json_repair
from loguru import logger
from openai import AsyncOpenAI

from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class CustomProvider(LLMProvider):

    def __init__(self, api_key: str = "no-key", api_base: str = "http://localhost:8000/v1", default_model: str = "default"):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        # Keep affinity stable for this provider instance to improve backend cache locality.
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_base,
            default_headers={"x-session-affinity": uuid.uuid4().hex},
        )

    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None,
                   model: str | None = None, max_tokens: int = 4096, temperature: float = 0.7,
                   reasoning_effort: str | None = None) -> LLMResponse:
        sanitized = self._sanitize_empty_content(messages)
        # Flatten list-format content to plain strings for OpenAI-compatible endpoints
        # that don't support multimodal content blocks.
        for msg in sanitized:
            content = msg.get("content")
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        parts.append(item.get("text", ""))
                    elif isinstance(item, str):
                        parts.append(item)
                msg["content"] = "\n".join(p for p in parts if p) or None
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": sanitized,
            "max_tokens": max(1, max_tokens),
            "temperature": temperature,
        }
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        if tools:
            kwargs.update(tools=tools, tool_choice="auto")
        try:
            response = await self._client.chat.completions.create(**kwargs)
            return self._parse(response)
        except Exception as e:
            import traceback
            logger.error("CustomProvider exception: {}", str(e))
            logger.debug("Traceback:\n{}", traceback.format_exc())
            return LLMResponse(content=f"Error: {e}", finish_reason="error")

    def _parse(self, response: Any) -> LLMResponse:
        # Validate response structure
        if not response:
            return LLMResponse(content="Error: Empty response from API", finish_reason="error")
        
        if not hasattr(response, 'choices') or not response.choices:
            error_msg = f"Error: Invalid API response structure. Response: {response}"
            if hasattr(response, 'error'):
                error_msg = f"Error: {response.error}"
            return LLMResponse(content=error_msg, finish_reason="error")
        
        choice = response.choices[0]
        msg = choice.message
        tool_calls = [
            ToolCallRequest(id=tc.id, name=tc.function.name,
                            arguments=json_repair.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments)
            for tc in (msg.tool_calls or [])
        ]
        u = response.usage
        return LLMResponse(
            content=msg.content, tool_calls=tool_calls, finish_reason=choice.finish_reason or "stop",
            usage={"prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens, "total_tokens": u.total_tokens} if u else {},
            reasoning_content=getattr(msg, "reasoning_content", None) or None,
        )

    def get_default_model(self) -> str:
        return self.default_model

