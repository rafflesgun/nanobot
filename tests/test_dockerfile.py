from pathlib import Path


def test_default_docker_extras_include_telegram() -> None:
    dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile"

    assert "ARG NANOBOT_EXTRAS=whatsapp,telegram" in dockerfile.read_text(encoding="utf-8")
