from nanobot.doctor.types import DoctorCheckResult, DoctorReport, DoctorStatus


def test_doctor_report_counts_statuses() -> None:
    report = DoctorReport(
        mode="local",
        config_path="/app/config.json",
        workspace_path="/app/workspace",
        results=[
            DoctorCheckResult(section="config", check_id="config_loaded", status=DoctorStatus.OK, message="ok"),
            DoctorCheckResult(section="workspace", check_id="workspace_exists", status=DoctorStatus.WARN, message="warn"),
            DoctorCheckResult(section="providers", check_id="provider_probe", status=DoctorStatus.FAIL, message="fail"),
        ],
    )

    assert report.summary == {"ok": 1, "warn": 1, "fail": 1}
    assert report.has_failures is True


def test_doctor_check_result_json_shape_is_stable() -> None:
    result = DoctorCheckResult(
        section="config",
        check_id="env_resolution",
        status=DoctorStatus.FAIL,
        message="Environment variable TELEGRAM_TOKEN is not set",
        hint="Set TELEGRAM_TOKEN in the container environment",
    )

    payload = result.model_dump()

    assert payload["section"] == "config"
    assert payload["check_id"] == "env_resolution"
    assert payload["status"] == "fail"
    assert payload["hint"].startswith("Set TELEGRAM_TOKEN")
