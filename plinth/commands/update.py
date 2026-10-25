"""`plinth update`: merge the latest templates into every generated repository.

Each repository keeps a `plinth` branch holding plinth's untouched output. Update renders the
current templates with the project's current config onto that branch, then merges the branch
into the checked-out one. Git keeps the user's own changes and marks real conflicts.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from plinth import config as defaults
from plinth.model.loader import ConfigError
from plinth.model.plan import RepoPlan, build_plan
from plinth.model.workspace import find_workspace, load_project_config
from plinth.output.render import BLUEPRINTS_DIR, GENERATOR_VERSION, FileMap, render_plan
from plinth.output.write import INITIAL_COMMIT_MESSAGE, git, write_tree

BRANCH = defaults.TEMPLATE_BRANCH


@dataclass
class RepoUpdate:
    folder: str
    status: str  # merged, up to date, conflicts, skipped
    detail: str = ""
    conflicts: list[str] = field(default_factory=list)


@dataclass
class UpdateResult:
    repos: list[RepoUpdate]
    notes: list[str] = field(default_factory=list)


def update_project(project_dir: Path, blueprints_root: Path = BLUEPRINTS_DIR) -> UpdateResult:
    if shutil.which("git") is None:
        raise ConfigError("git is required for plinth update")
    workspace = find_workspace(project_dir)
    config, notes = load_project_config(workspace), []
    plan = build_plan(config)
    files = render_plan(plan, blueprints_root)

    results = [_update_repo(workspace.root / repo.folder, repo, files) for repo in plan.repos]
    gitops = next(r for r in results if r.folder == plan.gitops.folder)
    if workspace.legacy and gitops.status in ("merged", "up to date"):
        workspace.config_path.unlink()
        notes.append(f"removed {workspace.config_path}; the config now lives in {gitops.folder}")
    return UpdateResult(results, notes)


def _repo_files(files: FileMap, repo: RepoPlan) -> FileMap:
    prefix = repo.folder + "/"
    return {k[len(prefix) :]: v for k, v in files.items() if k.startswith(prefix)}


def _ok(path: Path, *args: str) -> bool:
    return git(path, *args).returncode == 0


def _out(path: Path, *args: str) -> str:
    return git(path, *args).stdout.strip()


def _ensure_branch(path: Path) -> str | None:
    """Make sure the template branch exists locally. Returns a reason if it cannot."""
    if _ok(path, "rev-parse", "-q", "--verify", f"refs/heads/{BRANCH}"):
        return None
    if _ok(path, "rev-parse", "-q", "--verify", f"refs/remotes/origin/{BRANCH}"):
        return None if _ok(path, "branch", BRANCH, f"origin/{BRANCH}") else "cannot create branch"
    # projects from before the template branch existed: plinth's own first commit
    for sha in _out(path, "rev-list", "--max-parents=0", "HEAD").split():
        if _out(path, "log", "-1", "--format=%s", sha) == INITIAL_COMMIT_MESSAGE:
            return None if _ok(path, "branch", BRANCH, sha) else "cannot create branch"
    return (
        f"no {BRANCH} branch and no plinth initial commit to start one from; "
        f"fetch it with `git fetch origin {BRANCH}:{BRANCH}`"
    )


def _commit_templates(path: Path, files: FileMap) -> str | None:
    """Replace the template branch's content with `files`. Returns an error, if any."""
    tmp = Path(tempfile.mkdtemp(prefix="plinth-update-"))
    tree = tmp / "tree"
    try:
        result = git(path, "worktree", "add", "-q", str(tree), BRANCH)
        if result.returncode != 0:
            return f"cannot check out {BRANCH}: {result.stderr.strip()}"
        git(tree, "rm", "-rq", "--ignore-unmatch", ".")
        write_tree(tree, files)
        git(tree, "add", "-A")
        if not _ok(tree, "diff", "--cached", "--quiet"):
            message = f"chore: update plinth templates to {GENERATOR_VERSION}"
            result = git(tree, "commit", "-q", "-m", message)
            if result.returncode != 0:
                return f"cannot commit to {BRANCH}: {result.stderr.strip()}"
        return None
    finally:
        git(path, "worktree", "remove", "--force", str(tree))
        shutil.rmtree(tmp, ignore_errors=True)


def _update_repo(path: Path, repo: RepoPlan, files: FileMap) -> RepoUpdate:
    def skip(detail: str) -> RepoUpdate:
        return RepoUpdate(repo.folder, "skipped", detail)

    if not path.is_dir():
        return skip("not found here; clone it next to the others to update it")
    top = _out(path, "rev-parse", "--show-toplevel")
    if not top or Path(top).resolve() != path.resolve():
        return skip("not a git repository")
    if _out(path, "status", "--porcelain"):
        return skip("has uncommitted changes; commit or stash them first")
    if _out(path, "branch", "--show-current") == BRANCH:
        return skip(f"{BRANCH} is checked out; switch to your working branch first")

    reason = _ensure_branch(path)
    if reason:
        return skip(reason)
    error = _commit_templates(path, _repo_files(files, repo))
    if error:
        return skip(error)

    if _ok(path, "merge-base", "--is-ancestor", BRANCH, "HEAD"):
        return RepoUpdate(repo.folder, "up to date")
    message = f"chore: merge plinth templates {GENERATOR_VERSION}"
    if _ok(path, "merge", "--no-edit", "-m", message, BRANCH):
        return RepoUpdate(repo.folder, "merged")
    conflicts = _out(path, "diff", "--name-only", "--diff-filter=U").splitlines()
    return RepoUpdate(repo.folder, "conflicts", conflicts=conflicts)


def run(args: argparse.Namespace) -> int:
    try:
        result = update_project(args.project_dir)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for note in result.notes:
        print(f"note: {note}")
    width = max(len(r.folder) for r in result.repos)
    for repo in result.repos:
        detail = f": {repo.detail}" if repo.detail else ""
        print(f"  {repo.folder:<{width}}  {repo.status}{detail}")
        for path in repo.conflicts:
            print(f"  {'':<{width}}    conflict: {path}")
    if any(r.status == "conflicts" for r in result.repos):
        print(
            "\nresolve the conflicts in those repositories, then `git commit` to finish the merge"
        )
        return 1
    if any(r.status == "merged" for r in result.repos):
        print(f"\nreview the merges, then push each repository: git push origin HEAD {BRANCH}")
    return 1 if any(r.status == "skipped" for r in result.repos) else 0
