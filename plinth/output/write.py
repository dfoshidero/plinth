"""Write rendered files to disk and initialise git repositories."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from plinth import config as defaults
from plinth.output.render import FileMap, is_executable

INITIAL_COMMIT_MESSAGE = "chore: initial commit"


class OutputExistsError(Exception):
    pass


def write_tree(root: Path, files: FileMap) -> None:
    for rel in sorted(files):
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(files[rel])
        if is_executable(rel):
            dest.chmod(0o755)


def write_project(
    target: Path, files: FileMap, repo_urls: dict[str, str], init_git: bool
) -> list[str]:
    """Write a whole project atomically: everything lands in a temp folder that is
    renamed into place only once it is complete. Returns warnings."""
    if target.exists():
        raise OutputExistsError(f"refusing to write into existing path: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{target.name}.", suffix=".plinth-tmp", dir=target.parent))
    try:
        write_tree(tmp, files)
        warnings = init_repos(tmp, repo_urls) if init_git else []
        if target.exists():
            raise OutputExistsError(f"refusing to write into existing path: {target}")
        os.rename(tmp, target)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return warnings


def init_repos(root: Path, repo_urls: dict[str, str]) -> list[str]:
    if shutil.which("git") is None:
        return ["git not found; repositories were not initialised"]
    warnings = []
    for folder, url in repo_urls.items():
        warning = init_repo(root / folder, url)
        if warning:
            warnings.append(warning)
    return warnings


def git(path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=path, capture_output=True, text=True, check=False)


def init_repo(path: Path, url: str) -> str | None:
    """git init, first commit, and the template branch `plinth update` merges from."""

    for args in (("init", "-q", "-b", "main"), ("remote", "add", "origin", url), ("add", "-A")):
        result = git(path, *args)
        if result.returncode != 0:
            return f"{path.name}: git {args[0]} failed: {result.stderr.strip()}"
    result = git(path, "commit", "-q", "-m", INITIAL_COMMIT_MESSAGE)
    if result.returncode != 0:
        return f"{path.name}: initialised but not committed: {result.stderr.strip()}"
    result = git(path, "branch", defaults.TEMPLATE_BRANCH)
    if result.returncode != 0:
        return f"{path.name}: no {defaults.TEMPLATE_BRANCH} branch: {result.stderr.strip()}"
    return None
