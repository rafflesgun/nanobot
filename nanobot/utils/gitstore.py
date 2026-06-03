"""Git-backed version control for memory files, using dulwich or system git."""

from __future__ import annotations

import io
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger


@dataclass
class CommitInfo:
    sha: str
    message: str
    timestamp: str

    def format(self, diff: str = "") -> str:
        header = f"## {self.message.splitlines()[0]}\n`{self.sha}` — {self.timestamp}\n"
        if diff:
            return f"{header}\n```diff\n{diff}\n```"
        return f"{header}\n(no file changes)"


@dataclass
class LineAge:
    """Age of a single line based on git blame."""

    age_days: int  # days since last modification


def _compute_line_ages(annotated) -> list[LineAge]:
    """Convert annotate results to per-line ages."""
    now = datetime.now(tz=timezone.utc).date()
    ages: list[LineAge] = []
    for (commit, _tree_entry), _line_bytes in annotated:
        dt = datetime.fromtimestamp(commit.commit_time, tz=timezone.utc).date()
        ages.append(LineAge(age_days=(now - dt).days))
    return ages


def _compute_line_ages_from_timestamps(timestamps: list[int]) -> list[LineAge]:
    """Convert UNIX timestamps to per-line ages."""
    now = datetime.now(tz=timezone.utc).date()
    return [
        LineAge(age_days=(now - datetime.fromtimestamp(ts, tz=timezone.utc).date()).days)
        for ts in timestamps
    ]


class GitStore:
    """Git-backed version control for memory files."""

    def __init__(self, workspace: Path, tracked_files: list[str]):
        self._workspace = workspace
        self._tracked_files = tracked_files

    def _run_git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=self._workspace, text=True, capture_output=True, check=False
        )

    def _use_dulwich(self) -> bool:
        try:
            import dulwich  # noqa: F401

            return True
        except Exception:
            return False

    def is_initialized(self) -> bool:
        return (self._workspace / ".git").is_dir()

    def init(self) -> bool:
        if self.is_initialized():
            return False

        self._workspace.mkdir(parents=True, exist_ok=True)
        if self._is_inside_git_repo():
            logger.warning(
                "Workspace {} is already inside a git repo; skipping nested repo initialization",
                self._workspace,
            )
            return False

        try:
            if self._use_dulwich():
                from dulwich import porcelain

                gitignore = self._workspace / ".gitignore"
                dream_entries = self._build_gitignore()
                if gitignore.exists():
                    existing = gitignore.read_text(encoding="utf-8")
                    existing_lines = set(existing.splitlines())
                    new_lines = [
                        line for line in dream_entries.splitlines() if line not in existing_lines
                    ]
                    if new_lines:
                        merged = existing.rstrip("\n") + "\n" + "\n".join(new_lines) + "\n"
                        gitignore.write_text(merged, encoding="utf-8")
                else:
                    gitignore.write_text(dream_entries, encoding="utf-8")
                for rel in self._tracked_files:
                    tracked = self._workspace / rel
                    tracked.parent.mkdir(parents=True, exist_ok=True)
                    if not tracked.exists():
                        tracked.write_text("", encoding="utf-8")
                porcelain.init(str(self._workspace))
                porcelain.add(str(self._workspace), paths=[".gitignore"] + self._tracked_files)
                porcelain.commit(
                    str(self._workspace),
                    message=b"init: nanobot memory store",
                    author=b"nanobot <nanobot@dream>",
                    committer=b"nanobot <nanobot@dream>",
                )
            else:
                gitignore = self._workspace / ".gitignore"
                dream_entries = self._build_gitignore()
                if gitignore.exists():
                    existing = gitignore.read_text(encoding="utf-8")
                    existing_lines = set(existing.splitlines())
                    new_lines = [
                        line for line in dream_entries.splitlines() if line not in existing_lines
                    ]
                    if new_lines:
                        merged = existing.rstrip("\n") + "\n" + "\n".join(new_lines) + "\n"
                        gitignore.write_text(merged, encoding="utf-8")
                else:
                    gitignore.write_text(dream_entries, encoding="utf-8")
                for rel in self._tracked_files:
                    tracked = self._workspace / rel
                    tracked.parent.mkdir(parents=True, exist_ok=True)
                    if not tracked.exists():
                        tracked.write_text("", encoding="utf-8")
                self._run_git("init")
                self._run_git("config", "user.name", "nanobot")
                self._run_git("config", "user.email", "nanobot@dream")
                self._run_git("add", ".gitignore", *self._tracked_files)
                self._run_git("commit", "-m", "init: nanobot memory store")
            logger.info("Git store initialized at {}", self._workspace)
            return True
<<<<<<< HEAD
        except Exception as exc:
            logger.warning("Git store init failed for {}: {}", self._workspace, exc)
=======
        except Exception:
            logger.exception("Git store init failed for {}", self._workspace)
>>>>>>> origin/main
            return False

    def auto_commit(self, message: str) -> str | None:
        if not self.is_initialized():
            return None
        try:
            if self._use_dulwich():
                from dulwich import porcelain

                st = porcelain.status(self._workspace)
                if not st.unstaged and not any(st.staged.values()):
                    return None
                msg_bytes = message.encode("utf-8") if isinstance(message, str) else message
                porcelain.add(
                    self._workspace, paths=[f.encode("utf-8") for f in self._tracked_files]
                )
                sha_bytes = porcelain.commit(
                    self._workspace,
                    message=msg_bytes,
                    author=b"nanobot <nanobot@dream>",
                    committer=b"nanobot <nanobot@dream>",
                )
                if sha_bytes is None:
                    return None
                return sha_bytes.hex()[:8]
            status = self._run_git("status", "--porcelain", *self._tracked_files)
            if not status.stdout.strip():
                return None
            self._run_git("add", *self._tracked_files)
            self._run_git("commit", "-m", message)
            sha = self._run_git("rev-parse", "--short=8", "HEAD")
            return sha.stdout.strip() or None
        except Exception:
            logger.exception("Git auto-commit failed: {}", message)
            return None

    def _resolve_sha(self, short_sha: str) -> bytes | None:
        try:
            from dulwich.repo import Repo

            with Repo(self._workspace) as repo:
                try:
                    sha = repo.refs[b"HEAD"]
                except KeyError:
                    return None

                while sha:
                    if sha.hex().startswith(short_sha):
                        return sha
                    commit = repo[sha]
                    if commit.type_name != b"commit":
                        break
                    sha = commit.parents[0] if commit.parents else None
            return None
        except Exception:
            return None

    def _is_inside_git_repo(self) -> bool:
        """Check if self._workspace is already inside a git repository.

        Walks up from self._workspace to the filesystem root, returning True
        if any parent directory contains a .git entry.

        Git worktrees and submodules can use a ``.git`` file instead of a
        directory, so we must treat either form as "already inside a repo".
        """
        current = self._workspace.resolve()
        while current != current.parent:
            if (current / ".git").exists():
                return True
            current = current.parent
        return False

    def _build_gitignore(self) -> str:
        dirs: set[str] = set()
        for f in self._tracked_files:
            parent = str(Path(f).parent)
            if parent != ".":
                dirs.add(parent)
        lines = ["/*"]
        for d in sorted(dirs):
            lines.append(f"!{d}/")
        for f in self._tracked_files:
            lines.append(f"!{f}")
        lines.append("!.gitignore")
        return "\n".join(lines) + "\n"

    def _line_ages_from_git_blame(self, file_path: str) -> list[LineAge]:
        """Compute per-line ages via system git blame porcelain output."""
        cp = self._run_git("blame", "--line-porcelain", "--", file_path)
        if cp.returncode != 0 or not cp.stdout.strip():
            return []

        timestamps: list[int] = []
        current_timestamp: int | None = None
        for line in cp.stdout.splitlines():
            if line.startswith("author-time "):
                try:
                    current_timestamp = int(line.split(" ", 1)[1])
                except ValueError:
                    current_timestamp = None
                continue
            if line.startswith("\t"):
                if current_timestamp is None:
                    return []
                timestamps.append(current_timestamp)

        return _compute_line_ages_from_timestamps(timestamps)

    def log(self, max_entries: int = 20) -> list[CommitInfo]:
        if not self.is_initialized():
            return []
        try:
            if self._use_dulwich():
                from dulwich.repo import Repo

                entries: list[CommitInfo] = []
                with Repo(self._workspace) as repo:
                    try:
                        head = repo.refs[b"HEAD"]
                    except KeyError:
                        return []
                    sha = head
                    while sha and len(entries) < max_entries:
                        commit = repo[sha]
                        if commit.type_name != b"commit":
                            break
                        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(commit.commit_time))
                        msg = commit.message.decode("utf-8", errors="replace").strip()
                        entries.append(CommitInfo(sha=sha.hex()[:8], message=msg, timestamp=ts))
                        sha = commit.parents[0] if commit.parents else None
                return entries
            cp = self._run_git(
                "log",
                f"--max-count={max_entries}",
                "--date=format:%Y-%m-%d %H:%M",
                "--pretty=format:%H%x1f%ad%x1f%s",
            )
            if cp.returncode != 0 or not cp.stdout.strip():
                return []
            entries: list[CommitInfo] = []
            for line in cp.stdout.splitlines():
                sha, ts, msg = line.split("\x1f", 2)
                entries.append(CommitInfo(sha=sha[:8], message=msg, timestamp=ts))
            return entries
        except Exception:
            logger.exception("Git log failed")
            return []

    def line_ages(self, file_path: str) -> list[LineAge]:
        """Compute the age of each line in a tracked file via git blame.

        Returns one LineAge per line, in order.
        Returns an empty list if the repo is not initialized, the file is
        empty, or annotation fails.
        """

        if not self.is_initialized():
            return []

        target = self._workspace / file_path
        if not target.exists() or target.stat().st_size == 0:
            return []

        if self._use_dulwich():
            try:
                from dulwich import porcelain

<<<<<<< HEAD
                annotated = porcelain.annotate(str(self._workspace), file_path)
                if annotated:
                    return _compute_line_ages(annotated)
            except Exception:
                logger.warning(
                    "Git line_ages annotate failed for {}; falling back to git blame", file_path
                )
=======
            annotated = porcelain.annotate(str(self._workspace), file_path)
        except Exception:
            logger.exception("Git line_ages annotate failed for {}", file_path)
            return []
>>>>>>> origin/main

        return self._line_ages_from_git_blame(file_path)

    def diff_commits(self, sha1: str, sha2: str) -> str:
        if not self.is_initialized():
            return ""
        try:
            if self._use_dulwich():
                from dulwich import porcelain

                full1 = self._resolve_sha(sha1)
                full2 = self._resolve_sha(sha2)
                if not full1 or not full2:
                    return ""
                out = io.BytesIO()
                porcelain.diff(self._workspace, commit=full1, commit2=full2, outstream=out)
                return out.getvalue().decode("utf-8", errors="replace")
            cp = self._run_git("diff", sha1, sha2, "--", *self._tracked_files)
            return cp.stdout if cp.returncode == 0 else ""
        except Exception:
            logger.exception("Git diff_commits failed")
            return ""

    def find_commit(self, short_sha: str, max_entries: int = 20) -> CommitInfo | None:
        for c in self.log(max_entries=max_entries):
            if c.sha.startswith(short_sha):
                return c
        return None

    def show_commit_diff(self, commit: str) -> tuple[CommitInfo, str] | None:
        info = self.find_commit(commit, max_entries=200)
        if info is None:
            return None
        commits = self.log(max_entries=200)
        idx = next((i for i, c in enumerate(commits) if c.sha == info.sha), None)
        if idx is None:
            return None
        if idx == len(commits) - 1:
            return info, ""
        parent = commits[idx + 1]
        return info, self.diff_commits(parent.sha, info.sha)

    def revert(self, commit: str) -> str | None:
        if not self.is_initialized():
            return None
        try:
            commits = self.log(max_entries=200)
            idx = next((i for i, c in enumerate(commits) if c.sha.startswith(commit)), None)
            if idx is None:
                return None
            if idx == len(commits) - 1:
                logger.warning("Git revert: cannot revert root commit {}", commit)
                return None
            target = commits[idx].sha
            parent = commits[idx + 1].sha
            if self._use_dulwich():
                from dulwich.repo import Repo

                restored: list[str] = []
                with Repo(self._workspace) as repo:
                    full_sha = self._resolve_sha(target)
                    if full_sha is None:
                        return None
                    commit_obj = repo[full_sha]
                    if not commit_obj.parents:
                        return None
                    parent_obj = repo[commit_obj.parents[0]]
                    tree = repo[parent_obj.tree]
                    for filepath in self._tracked_files:
                        content = self._read_blob_from_tree(repo, tree, filepath)
                        if content is not None:
                            dest = self._workspace / filepath
                            dest.write_text(content, encoding="utf-8")
                            restored.append(filepath)
                if not restored:
                    return None
            else:
                cp = self._run_git("checkout", parent, "--", *self._tracked_files)
                if cp.returncode != 0:
                    return None
            return self.auto_commit(f"revert: undo {target}")
        except Exception:
            logger.exception("Git revert failed for {}", commit)
            return None

    @staticmethod
    def _read_blob_from_tree(repo, tree, filepath: str) -> str | None:
        parts = Path(filepath).parts
        current = tree
        for part in parts:
            try:
                entry = current[part.encode()]
            except KeyError:
                return None
            obj = repo[entry[1]]
            if obj.type_name == b"blob":
                return obj.data.decode("utf-8", errors="replace")
            if obj.type_name == b"tree":
                current = obj
            else:
                return None
        return None
