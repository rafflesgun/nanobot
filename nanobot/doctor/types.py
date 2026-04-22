from enum import StrEnum

from pydantic import BaseModel, Field


class DoctorStatus(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


class DoctorCheckResult(BaseModel):
    section: str
    check_id: str
    status: DoctorStatus
    message: str
    hint: str | None = None


class DoctorReport(BaseModel):
    mode: str
    config_path: str
    workspace_path: str
    results: list[DoctorCheckResult] = Field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        counts = {"ok": 0, "warn": 0, "fail": 0}
        for result in self.results:
            counts[result.status.value] += 1
        return counts

    @property
    def has_failures(self) -> bool:
        return self.summary["fail"] > 0
