from nanobot.cli import commands


def test_gateway_imports_admin_server_for_http_surface():
    source = commands._run_gateway.__code__.co_names

    assert "serve_gateway_http" in source
    assert "AdminContext" in source
