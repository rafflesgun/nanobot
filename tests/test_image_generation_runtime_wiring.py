import ast
import inspect
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import nanobot.agent.loop as loop_module
import nanobot.cli.commands as cli_commands
import nanobot.nanobot as nanobot_facade
from nanobot.agent.loop import AgentLoop
from nanobot.agent.tools.image_generation import GenerateImageTool
from nanobot.bus import MessageBus
from nanobot.config.schema import Config


def _from_config_calls(function) -> list[ast.Call]:
    """Find AgentLoop.from_config(...) calls in *function* source."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_config"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "AgentLoop"
    ]


def _keyword_value(call: ast.Call, name: str) -> ast.expr | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _is_attribute_chain(node: ast.expr, chain: tuple[str, ...]) -> bool:
    if not chain:
        return False
    if len(chain) == 1:
        return isinstance(node, ast.Name) and node.id == chain[0]
    return (
        isinstance(node, ast.Attribute)
        and node.attr == chain[-1]
        and _is_attribute_chain(node.value, chain[:-1])
    )


def _function_tree(function) -> ast.Module:
    return ast.parse(textwrap.dedent(inspect.getsource(function)))


def _calls_method(node: ast.AST, receiver: str, method: str, args: tuple[str, ...]) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if not isinstance(node.func, ast.Attribute) or node.func.attr != method:
        return False
    if not isinstance(node.func.value, ast.Name) or node.func.value.id != receiver:
        return False
    if len(node.args) != len(args):
        return False
    return all(isinstance(arg, ast.Name) and arg.id == expected for arg, expected in zip(node.args, args))


# -- AgentLoop direct tests ---------------------------------------------------

def test_agent_loop_registers_image_generation_when_tools_config_enables(tmp_path: Path) -> None:
    """Image generation is always registered via ToolLoader when tools config enables it."""
    config = Config.model_validate(
        {
            "providers": {"openai": {"apiKey": "image-key", "apiBase": "https://api.openai.com/v1"}},
            "tools": {"imageGeneration": {"enabled": True}},
        }
    )
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"

    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        tools_config=config.tools,
        image_generation_provider_config=config.providers.openai,
    )

    assert isinstance(loop.tools.get("generate_image"), GenerateImageTool)


def test_agent_loop_registers_image_generation_with_custom_provider(tmp_path: Path) -> None:
    config = Config.model_validate(
        {
            "providers": {
                "custom": {
                    "apiKey": "image-key",
                    "apiBase": "https://images.example.test/v1",
                }
            },
            "tools": {"imageGeneration": {"enabled": True, "provider": "custom"}},
        }
    )
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"

    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        tools_config=config.tools,
        image_generation_provider_configs={"custom": config.providers.custom},
    )

    assert isinstance(loop.tools.get("generate_image"), GenerateImageTool)


def test_agent_loop_imports_image_generation_only_inside_enabled_registration_block() -> None:
    source = Path(loop_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)]

    assert all(node.module != "nanobot.agent.tools.image_generation" for node in top_level_imports)
    assert all(node.module != "nanobot.image_generation" for node in top_level_imports)


# -- CLI serve tests ----------------------------------------------------------

def test_serve_passes_image_generation_provider_configs() -> None:
    """The serve command passes image_generation_provider_configs to AgentLoop."""
    calls = _from_config_calls(cli_commands.serve)

    assert len(calls) == 1
    value = _keyword_value(calls[0], "image_generation_provider_configs")
    assert value is not None


# -- Gateway tests ------------------------------------------------------------

def test_gateway_passes_image_generation_provider_configs() -> None:
    """The gateway passes image_generation_provider_configs via from_config."""
    calls = _from_config_calls(cli_commands._run_gateway)

    assert len(calls) == 1
    value = _keyword_value(calls[0], "image_generation_provider_configs")
    assert value is not None
    assert isinstance(value, ast.Call)
    assert isinstance(value.func, ast.Name)
    assert value.func.id == "image_gen_provider_configs"


def test_gateway_no_longer_imports_generate_image_tool() -> None:
    """The gateway no longer imports GenerateImageTool explicitly;
    ToolLoader handles registration."""
    tree = _function_tree(cli_commands._run_gateway)
    imports_generate_image_tool = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "nanobot.agent.tools.image_generation"
        and any(alias.name == "GenerateImageTool" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert not imports_generate_image_tool


# -- CLI agent tests ----------------------------------------------------------

def test_cli_agent_passes_image_generation_provider_configs() -> None:
    """The CLI agent command passes image_generation_provider_configs via from_config."""
    calls = _from_config_calls(cli_commands.agent)

    assert len(calls) == 1
    value = _keyword_value(calls[0], "image_generation_provider_configs")
    assert value is not None


# -- Programmatic nanobot tests ------------------------------------------------

def test_programmatic_nanobot_passes_image_generation_provider_configs() -> None:
    """Nanobot.from_config passes image_generation_provider_configs."""
    calls = _from_config_calls(nanobot_facade.Nanobot.from_config.__func__)

    assert len(calls) == 1
    value = _keyword_value(calls[0], "image_generation_provider_configs")
    assert value is not None
