from nanobot.admin.auth import bearer_token, is_authorized
from nanobot.config.schema import Config


def test_gateway_admin_defaults_are_disabled():
    cfg = Config()

    assert cfg.gateway.admin.enabled is False
    assert cfg.gateway.admin.token == ""
    assert cfg.gateway.admin.max_log_tail_lines == 1000
    assert cfg.gateway.admin.request_timeout_s == 10.0


def test_gateway_admin_accepts_camel_case_config():
    cfg = Config.model_validate(
        {
            "gateway": {
                "admin": {
                    "enabled": True,
                    "token": "secret",
                    "maxLogTailLines": 250,
                    "requestTimeoutS": 3.5,
                }
            }
        }
    )

    assert cfg.gateway.admin.enabled is True
    assert cfg.gateway.admin.token == "secret"
    assert cfg.gateway.admin.max_log_tail_lines == 250
    assert cfg.gateway.admin.request_timeout_s == 3.5


def test_bearer_token_extracts_case_insensitive_header():
    assert bearer_token({"Authorization": "Bearer abc"}) == "abc"
    assert bearer_token({"authorization": "Bearer abc"}) == "abc"
    assert bearer_token({"Authorization": "Basic abc"}) is None
    assert bearer_token({"Authorization": "Bearer   "}) is None


def test_bearer_token_extracts_mixed_case_authorization_header():
    assert bearer_token({"AUTHORIZATION": "Bearer upper"}) == "upper"
    assert bearer_token({"AuthoriZation": "Bearer mixed"}) == "mixed"


def test_is_authorized_requires_enabled_and_token():
    assert is_authorized({"Authorization": "Bearer secret"}, enabled=False, configured_token="secret") is False
    assert is_authorized({"Authorization": "Bearer secret"}, enabled=True, configured_token="") is False
    assert is_authorized({"Authorization": "Bearer wrong"}, enabled=True, configured_token="secret") is False
    assert is_authorized({"Authorization": "Bearer secret"}, enabled=True, configured_token="secret") is True
