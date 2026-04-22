from pathlib import Path

from nanobot.doctor.checks.workspace import run_workspace_checks


def test_workspace_checks_report_missing_workspace(tmp_path: Path) -> None:
    results = run_workspace_checks(tmp_path / "workspace")
    assert any(r.check_id == "workspace_exists" and r.status.value == "fail" for r in results)


def test_workspace_checks_report_required_runtime_dirs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    results = run_workspace_checks(workspace)

    assert any(r.check_id == "memory_dir" for r in results)
    assert any(r.check_id == "sessions_dir" for r in results)
    assert any(r.check_id == "cron_dir" for r in results)
    assert any(r.check_id == "skills_dir" for r in results)
    assert any(r.check_id == "skill_proposals_dir" for r in results)


def test_workspace_checks_all_pass_when_dirs_exist(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for subdir in ["memory", "sessions", "cron", "skills", "skill_proposals"]:
        (workspace / subdir).mkdir()

    results = run_workspace_checks(workspace)
    assert all(r.status.value == "ok" for r in results)


def test_workspace_checks_report_not_writable(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    workspace.chmod(0o444)

    try:
        results = run_workspace_checks(workspace)
        assert any(r.check_id == "workspace_writable" and r.status.value == "fail" for r in results)
    finally:
        workspace.chmod(0o755)


def test_workspace_checks_warn_missing_subdirs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    results = run_workspace_checks(workspace)
    subdir_checks = [r for r in results if r.check_id not in ("workspace_exists", "workspace_writable")]
    # Missing subdirs should warn (they can be created at runtime)
    assert all(r.status.value == "warn" for r in subdir_checks)
