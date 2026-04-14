"""Tests for OpenAICompatProvider handling custom/direct endpoints."""

import httpx
from types import SimpleNamespace
from unittest.mock import patch

from nanobot.providers.openai_compat_provider import OpenAICompatProvider
from nanobot.providers.registry import find_by_name


def test_custom_provider_parse_handles_empty_choices() -> None:
    with patch("nanobot.providers.openai_compat_provider.AsyncOpenAI"):
        provider = OpenAICompatProvider()
    response = SimpleNamespace(choices=[])

    result = provider._parse(response)

    assert result.finish_reason == "error"
    assert "empty choices" in result.content


def test_custom_provider_parse_accepts_plain_string_response() -> None:
    with patch("nanobot.providers.openai_compat_provider.AsyncOpenAI"):
        provider = OpenAICompatProvider()

    result = provider._parse("hello from backend")

    assert result.finish_reason == "stop"
    assert result.content == "hello from backend"


def test_custom_provider_parse_accepts_dict_response() -> None:
    with patch("nanobot.providers.openai_compat_provider.AsyncOpenAI"):
        provider = OpenAICompatProvider()

    result = provider._parse(
        {
            "choices": [
                {
                    "message": {"content": "hello from dict"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 2,
                "total_tokens": 3,
            },
        }
    )

    assert result.finish_reason == "stop"
    assert result.content == "hello from dict"
    assert result.usage["total_tokens"] == 3


def test_custom_provider_parse_chunks_accepts_plain_text_chunks() -> None:
    result = OpenAICompatProvider._parse_chunks(["hello ", "world"])

    assert result.finish_reason == "stop"
    assert result.content == "hello world"


def test_custom_provider_client_disables_sdk_retries_and_sets_timeout() -> None:
    with patch("nanobot.providers.openai_compat_provider.AsyncOpenAI") as mock_client:
        OpenAICompatProvider(api_key="test-key", api_base="https://example.com/v1")

    kwargs = mock_client.call_args.kwargs
    assert kwargs["max_retries"] == 0
    assert kwargs["timeout"] == httpx.Timeout(180.0, connect=10.0)


def test_local_provider_502_error_includes_reachability_hint() -> None:
    spec = find_by_name("ollama")
    with patch("nanobot.providers.openai_compat_provider.AsyncOpenAI"):
        provider = OpenAICompatProvider(api_base="http://localhost:11434/v1", spec=spec)

    result = provider._handle_error(
        Exception("Error code: 502"),
        spec=spec,
        api_base="http://localhost:11434/v1",
    )

    assert result.finish_reason == "error"
    assert "local model endpoint" in result.content
    assert "http://localhost:11434/v1" in result.content
    assert "proxy/tunnel" in result.content
