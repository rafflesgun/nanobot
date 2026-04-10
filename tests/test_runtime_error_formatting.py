from nanobot.utils.runtime import (
    PROVIDER_ERROR_FRIENDLY,
    format_provider_error,
    is_provider_error_message,
)


def test_is_provider_error_message_detects_new_api_error_payload() -> None:
    content = (
        'Error: {"message": "system cpu overloaded (current: 100.0%, threshold: 90%)", '
        '"type": "new_api_error", "param": "", "code": "system_cpu_overloaded"}'
    )

    assert is_provider_error_message(content) is True


def test_format_provider_error_rewrites_new_api_error_payload() -> None:
    content = (
        'Error: {"message": "system cpu overloaded (current: 100.0%, threshold: 90%)", '
        '"type": "new_api_error", "param": "", "code": "system_cpu_overloaded"}'
    )

    assert format_provider_error(content) == PROVIDER_ERROR_FRIENDLY
