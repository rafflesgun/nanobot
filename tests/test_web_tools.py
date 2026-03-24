"""Tests for web tools: WebSearchTool and WebFetchTool."""

import pytest
from unittest.mock import patch, MagicMock, Mock


class TestWebSearchTool:
    """Tests for WebSearchTool using ddgs library."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        """Test that search returns formatted results."""
        from nanobot.agent.tools.web import WebSearchTool

        mock_results = [
            {"title": "Python", "href": "https://python.org", "body": "Python is a programming language."},
            {"title": "Tutorial", "href": "https://example.com/tutorial", "body": "Learn Python."},
        ]

        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_results)

            tool = WebSearchTool()
            result = await tool.execute("python", count=2)

        assert "Results for: python" in result
        assert "Python" in result
        assert "https://python.org" in result

    @pytest.mark.asyncio
    async def test_search_no_results(self):
        """Test that search handles no results gracefully."""
        from nanobot.agent.tools.web import WebSearchTool

        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=[])

            tool = WebSearchTool()
            result = await tool.execute("nonexistentquery12345")

        assert "No results for: nonexistentquery12345" in result

    @pytest.mark.asyncio
    async def test_search_handles_exception(self):
        """Test that search handles exceptions gracefully."""
        from nanobot.agent.tools.web import WebSearchTool

        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                side_effect=Exception("Network error")
            )

            tool = WebSearchTool()
            result = await tool.execute("test")

        assert "Error:" in result
        assert "Network error" in result

    def test_initialization_with_proxy(self):
        """Test that tool stores proxy parameter."""
        from nanobot.agent.tools.web import WebSearchTool

        tool = WebSearchTool(proxy="http://127.0.0.1:7890")
        assert tool.proxy == "http://127.0.0.1:7890"

    def test_initialization_without_proxy(self):
        """Test that tool works without proxy."""
        from nanobot.agent.tools.web import WebSearchTool

        tool = WebSearchTool()
        assert tool.proxy is None
        assert tool.max_results == 5


class TestWebFetchTool:
    """Tests for WebFetchTool."""

    def test_url_validation_valid(self):
        """Test URL validation with valid URLs."""
        from nanobot.agent.tools.web import _validate_url

        valid, error = _validate_url("https://example.com")
        assert valid is True
        assert error == ""

        valid, error = _validate_url("http://example.com/path")
        assert valid is True
        assert error == ""

    def test_url_validation_invalid_scheme(self):
        """Test URL validation with invalid schemes."""
        from nanobot.agent.tools.web import _validate_url

        valid, error = _validate_url("ftp://example.com")
        assert valid is False
        assert "http/https" in error.lower()

        valid, error = _validate_url("file:///etc/passwd")
        assert valid is False

    def test_url_validation_missing_domain(self):
        """Test URL validation with missing domain."""
        from nanobot.agent.tools.web import _validate_url

        valid, error = _validate_url("https://")
        assert valid is False
        assert "domain" in error.lower()


class AsyncMock(Mock):
    """Helper for async mocking."""
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)
