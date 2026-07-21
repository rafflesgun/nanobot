"""Cross-suite test infrastructure."""

from __future__ import annotations

import os
import shutil
import ssl
import sys
from collections.abc import Iterator
from pathlib import Path

import certifi
import pytest
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def pytest_collection_modifyitems(config, items):
    has_riva_client = shutil.which("python3") is not None
    try:
        import riva.client  # noqa: F401
    except Exception:
        has_riva_client = False

    has_riva_env = bool(os.getenv("NVIDIA_API_KEY"))
    needs_riva = pytest.mark.skip(
        reason="Riva integration test requires riva client and NVIDIA_API_KEY"
    )

    if has_riva_client and has_riva_env:
        return

    for item in items:
        if item.nodeid in {
            "tests/test_riva_config.py::test_riva_config",
            "tests/test_riva_tts.py::test_riva_tts",
            "tests/test_voice_parsing.py::test_voice_parsing",
        }:
            item.add_marker(needs_riva)
@pytest.fixture(scope="session", autouse=True)
def _use_windows_system_ca_for_default_http_clients() -> Iterator[None]:
    """Avoid reparsing certifi's CA bundle for every offline HTTP client.

    Loading certifi takes roughly 0.7 seconds per client on Windows. The test
    suite constructs hundreds of clients while mocking their I/O. System roots
    preserve certificate verification for accidental local requests; explicit
    ``cafile``, ``capath``, and ``cadata`` arguments still use the real loader.
    """
    if sys.platform != "win32":
        yield
        return

    original = ssl.create_default_context
    certifi_path = os.path.normcase(os.path.abspath(certifi.where()))

    def create_default_context(
        purpose: ssl.Purpose = ssl.Purpose.SERVER_AUTH,
        *,
        cafile: str | None = None,
        capath: str | None = None,
        cadata: str | bytes | None = None,
    ) -> ssl.SSLContext:
        requested_path = os.path.normcase(os.path.abspath(cafile)) if cafile else None
        if requested_path == certifi_path and capath is None and cadata is None:
            return original(purpose)
        return original(
            purpose,
            cafile=cafile,
            capath=capath,
            cadata=cadata,
        )

    ssl.create_default_context = create_default_context
    try:
        yield
    finally:
        ssl.create_default_context = original
