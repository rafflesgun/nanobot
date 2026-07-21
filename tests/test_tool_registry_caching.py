"""Tests for tool registry caching functionality."""


from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.registry import ToolRegistry


class TestTool(Tool):
    @property
    def name(self) -> str:
        return "test_tool"

    @property
    def description(self) -> str:
        return "A test tool"

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string"},
            },
        }

    async def execute(self, **kwargs):
        return "success"


class AnotherTool(Tool):
    @property
    def name(self) -> str:
        return "another_tool"

    @property
    def description(self) -> str:
        return "Another test tool"

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "param2": {"type": "integer"},
            },
        }

    async def execute(self, **kwargs):
        return "success"


def test_registry_caching_basic():
    """Test that get_definitions caches results after first call."""
    registry = ToolRegistry()
    tool = TestTool()
    registry.register(tool)

    # First call - should populate cache
    defs1 = registry.get_definitions()

    # Second call - should return cached result
    defs2 = registry.get_definitions()

    # Should be the same object (cached)
    assert defs1 is defs2

    # Should contain the expected tool definition
    assert len(defs1) == 1
    assert defs1[0]["function"]["name"] == "test_tool"


def test_registry_caching_after_registration():
    """Test that cache is invalidated after registration."""
    registry = ToolRegistry()
    tool1 = TestTool()
    registry.register(tool1)

    # Get definitions once to populate cache
    defs1 = registry.get_definitions()

    # Register another tool
    registry.register(AnotherTool())

    # Cache should be invalidated, so new call should return fresh result
    defs2 = registry.get_definitions()

    # Should be different objects (freshly computed)
    assert defs1 is not defs2
    assert len(defs2) == 2
    # Tools are sorted alphabetically, so "another_tool" comes before "test_tool"
    names = [d["function"]["name"] for d in defs2]
    assert set(names) == {"another_tool", "test_tool"}


def test_registry_caching_after_unregistration():
    """Test that cache is invalidated after unregistration."""
    registry = ToolRegistry()
    tool1 = TestTool()
    tool2 = AnotherTool()
    registry.register(tool1)
    registry.register(tool2)

    # Get definitions once to populate cache
    defs1 = registry.get_definitions()

    # Unregister a tool
    registry.unregister("test_tool")

    # Cache should be invalidated, so new call should return fresh result
    defs2 = registry.get_definitions()

    # Should be different objects (freshly computed)
    assert defs1 is not defs2
    assert len(defs2) == 1
    assert defs2[0]["function"]["name"] == "another_tool"


def test_registry_empty_cache():
    """Test that empty registry returns empty list without caching issues."""
    registry = ToolRegistry()

    # Should return empty list
    defs = registry.get_definitions()
    assert defs == []

    # Second call should also return empty list and be cached
    defs2 = registry.get_definitions()
    assert defs is defs2


def test_registry_multiple_calls_same_cache():
    """Test that multiple calls to get_definitions return the same cached object."""
    registry = ToolRegistry()
    tool = TestTool()
    registry.register(tool)

    # Multiple calls should return the same cached object
    defs_list = [registry.get_definitions() for _ in range(5)]
    for defs in defs_list:
        assert defs is defs_list[0]
