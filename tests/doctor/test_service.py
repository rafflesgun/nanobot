from pathlib import Path

from nanobot.doctor.service import DoctorService


def test_doctor_service_aggregates_sections(tmp_path: Path) -> None:
    service = DoctorService()
    report = service.run(
        config_path=tmp_path / "config.json",
        workspace=tmp_path / "workspace",
        live=False,
    )

    sections = {result.section for result in report.results}
    assert "config" in sections
    assert "workspace" in sections


def test_doctor_service_preserves_mode(tmp_path: Path) -> None:
    service = DoctorService()
    report = service.run(
        config_path=tmp_path / "config.json",
        workspace=tmp_path / "workspace",
        live=True,
    )

    assert report.mode == "live"
