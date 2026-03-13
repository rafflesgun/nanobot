# GitHub Copilot Tools Capability Check (March 2026)

Current workspace: `/Users/raffles/git/nanobot-rg`

Open file: `nanobot/channels/telegram.py`

## What I know without calling tools right now

- Project has multi-channel support (Telegram, Discord, Slack, WeCom, Feishu, DingTalk, Matrix, QQ, Email, …)
- Core uses event bus + cron + heartbeat pattern
- Bridge folder contains TypeScript code (whatsapp.ts, server.ts)
- Many targeted tests: test_telegram_channel.py, test_cron_topic_delivery.py, etc.
- Using pyproject.toml → modern Python packaging

## Things I can do immediately (tool-assisted)

1. Read any source file → e.g. show structure/content of telegram.py
2. Grep or semantic search across codebase
   - "telegram bot token"
   - "BaseChannel subclass"
   - "cron.*deliver"
3. List files matching pattern → e.g. all *channel*.py files
4. Show git changed files or last commit message
5. Run small commands → e.g. `ls -la nanobot/channels`, `pip list`, `pytest -k telegram -v`
6. Install Python packages if needed
7. Propose precise search & replace edits in any file
8. Create more files / folders / structured TODO lists

## Quick test I can run right now (if you want)

Pick any line below — just say the number or describe what you'd like to see:

1. Show first 25 lines of `nanobot/channels/telegram.py`
2. List all channel module names (dingtalk.py, discord.py, …)
3. Find every file that imports `BaseChannel`
4. Run `pytest tests/test_telegram_channel.py -v` and show result
5. Show currently installed top-level Python packages
6. Create folder `tmp-test/` + empty file inside
7. Grep for "cron" OR "heartbeat" in nanobot/ folder
8. Show git status (changed/staged files)

Just reply with a number or tell me what kind of check / action you'd like to try next!
