from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, Field


class SkillScanFinding(BaseModel):
    severity: str
    category: str
    pattern_id: str
    message: str
    match: str | None = None


class SkillScanResult(BaseModel):
    verdict: str
    findings: list[SkillScanFinding] = Field(default_factory=list)


@dataclass(frozen=True)
class _Rule:
    pattern_id: str
    severity: str
    category: str
    message: str
    pattern: re.Pattern[str]


_RULES = (
    _Rule(
        pattern_id="env_exfil_curl",
        severity="critical",
        category="exfiltration",
        message="Potential environment secret exfiltration via curl.",
        pattern=re.compile(r"curl\s+https?://\S*\$[A-Z_][A-Z0-9_]*", re.IGNORECASE),
    ),
    _Rule(
        pattern_id="prompt_injection_ignore_rules",
        severity="high",
        category="prompt injection / deception",
        message="Instruction attempts to bypass prior safety constraints.",
        pattern=re.compile(r"ignore\s+(all\s+)?(previous|prior|earlier)\s+instructions", re.IGNORECASE),
    ),
    _Rule(
        pattern_id="destructive_rm_rf",
        severity="high",
        category="destructive shell patterns",
        message="Potentially destructive recursive delete command.",
        pattern=re.compile(r"rm\s+-rf\b", re.IGNORECASE),
    ),
    _Rule(
        pattern_id="persistence_cron",
        severity="medium",
        category="persistence",
        message="Cron usage can establish or inspect persistence.",
        pattern=re.compile(r"\bcrontab\b", re.IGNORECASE),
    ),
    _Rule(
        pattern_id="obfuscation_base64_exec",
        severity="medium",
        category="obfuscation",
        message="Base64-decoded shell execution can hide behavior.",
        pattern=re.compile(r"base64\s+-d|python\s+-c|bash\s+-c", re.IGNORECASE),
    ),
)

_BLOCK_SEVERITIES = {"critical", "high"}


def scan_skill_content(name: str, content: str) -> SkillScanResult:
    del name

    findings: list[SkillScanFinding] = []
    for rule in _RULES:
        match = rule.pattern.search(content)
        if match is None:
            continue
        findings.append(
            SkillScanFinding(
                severity=rule.severity,
                category=rule.category,
                pattern_id=rule.pattern_id,
                message=rule.message,
                match=match.group(0),
            )
        )

    if not findings:
        return SkillScanResult(verdict="safe")
    if any(finding.severity in _BLOCK_SEVERITIES for finding in findings):
        return SkillScanResult(verdict="block", findings=findings)
    return SkillScanResult(verdict="warn", findings=findings)
