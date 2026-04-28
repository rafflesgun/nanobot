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


def _agent_loop_calls(function) -> list[ast.Call]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "AgentLoop"
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


def test_agent_loop_does_not_register_image_generation_without_runtime_opt_in(tmp_path: Path) -> None:
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
        image_generation_provider=config.providers.openai,
    )

    assert loop.tools.get("generate_image") is None


def test_agent_loop_registers_image_generation_with_runtime_opt_in(tmp_path: Path) -> None:
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
        image_generation_provider=config.providers.openai,
        enable_image_generation_tool=True,
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
        image_generation_provider=config.get_image_generation_provider(),
        enable_image_generation_tool=True,
    )

    assert isinstance(loop.tools.get("generate_image"), GenerateImageTool)


def test_agent_loop_imports_image_generation_only_inside_enabled_registration_block() -> None:
    source = Path(loop_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)]

    assert all(node.module != "nanobot.agent.tools.image_generation" for node in top_level_imports)
    assert all(node.module != "nanobot.image_generation" for node in top_level_imports)


def test_serve_agent_loop_does_not_enable_image_generation() -> None:
    calls = _agent_loop_calls(cli_commands.serve)

    assert len(calls) == 1
    value = _keyword_value(calls[0], "enable_image_generation_tool")
    assert value is None or (isinstance(value, ast.Constant) and value.value is False)


def test_gateway_agent_loop_passes_openai_provider() -> None:
    calls = _agent_loop_calls(cli_commands._run_gateway)

    assert len(calls) == 1
    value = _keyword_value(calls[0], "image_generation_provider")
    assert value is not None
    assert isinstance(value, ast.Call)
    assert isinstance(value.func, ast.Attribute)
    assert value.func.attr == "get_image_generation_provider"
    assert _is_attribute_chain(value.func.value, ("config",))


def test_gateway_agent_loop_enables_image_generation() -> None:
    calls = _agent_loop_calls(cli_commands._run_gateway)

    assert len(calls) == 1
    value = _keyword_value(calls[0], "enable_image_generation_tool")
    assert isinstance(value, ast.Constant)
    assert value.value is True


def test_cli_agent_loop_does_not_enable_image_generation() -> None:
    calls = _agent_loop_calls(cli_commands.agent)

    assert len(calls) == 1
    value = _keyword_value(calls[0], "enable_image_generation_tool")
    assert value is None or (isinstance(value, ast.Constant) and value.value is False)


def test_programmatic_nanobot_does_not_enable_image_generation() -> None:
    calls = _agent_loop_calls(nanobot_facade.Nanobot.from_config.__func__)

    assert len(calls) == 1
    value = _keyword_value(calls[0], "enable_image_generation_tool")
    assert value is None or (isinstance(value, ast.Constant) and value.value is False)


def test_gateway_routes_image_generation_outputs_to_channels() -> None:
    tree = _function_tree(cli_commands._run_gateway)
    imports_generate_image_tool = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "nanobot.agent.tools.image_generation"
        and any(alias.name == "GenerateImageTool" for alias in node.names)
        for node in ast.walk(tree)
    )
    image_tool_lookup = any(
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "image_tool" for target in node.targets)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "get"
        and node.value.args
        and isinstance(node.value.args[0], ast.Constant)
        and node.value.args[0].value == "generate_image"
        for node in ast.walk(tree)
    )
    callback_wired_after_type_check = any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Call)
        and isinstance(node.test.func, ast.Name)
        and node.test.func.id == "isinstance"
        and len(node.test.args) == 2
        and isinstance(node.test.args[0], ast.Name)
        and node.test.args[0].id == "image_tool"
        and isinstance(node.test.args[1], ast.Name)
        and node.test.args[1].id == "GenerateImageTool"
        and any(
            _calls_method(child, "image_tool", "set_send_callback", ("_deliver_to_channel",))
            for child in ast.walk(node)
        )
        for node in ast.walk(tree)
    )

    assert imports_generate_image_tool
    assert image_tool_lookup
    assert callback_wired_after_type_check
