# Tool Usage Notes

Tool signatures are provided automatically via function calling.
This file documents non-obvious constraints and usage patterns.

## exec — Safety Limits

- Commands have a configurable timeout (default 60s)
- Dangerous commands are blocked (rm -rf, format, dd, shutdown, etc.)
- Output is truncated at 10,000 characters
- `restrictToWorkspace.enabled` can limit file access and shell working directories to the workspace
- `restrictToWorkspace.extraRead` and `restrictToWorkspace.extraWrite` extend that allowlist when needed

## cron — Scheduled Reminders

- Please refer to cron skill for usage.
