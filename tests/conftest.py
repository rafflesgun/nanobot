import os
import shutil

import pytest


def pytest_collection_modifyitems(config, items):
    has_riva_client = shutil.which("python3") is not None
    try:
        import riva.client  # noqa: F401
    except Exception:
        has_riva_client = False

    has_riva_env = bool(os.getenv("NVIDIA_API_KEY"))
    needs_riva = pytest.mark.skip(reason="Riva integration test requires riva client and NVIDIA_API_KEY")

    if has_riva_client and has_riva_env:
        return

    for item in items:
        if item.nodeid in {
            "tests/test_riva_config.py::test_riva_config",
            "tests/test_riva_tts.py::test_riva_tts",
            "tests/test_voice_parsing.py::test_voice_parsing",
        }:
            item.add_marker(needs_riva)
