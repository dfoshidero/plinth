"""Run the generated scripts/ci.sh for real; docker is replaced by a stub that records calls."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest
import yaml

from plinth.loader import parse_config
from plinth.plan import build_plan
from plinth.render import render_plan
from plinth.write import write_tree

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")

DOCKER_STUB = """#!/bin/sh
case "$1" in
  login) cat >/dev/null ;;
  build|push) echo "$*" >>"$DOCKER_LOG" ;;
  image) for a; do last=$a; done; echo "${last%:*}@sha256:0123abcd" ;;
esac
"""

REJECT_FIRST_PUSH = """#!/bin/sh
if [ ! -f "$GIT_DIR/rejected-once" ]; then
  touch "$GIT_DIR/rejected-once"
  echo "simulated concurrent push" >&2
  exit 1
fi
"""


def run(cwd, *args, env=None, check=True):
    result = subprocess.run(
        list(args), cwd=cwd, capture_output=True, text=True, env=env, check=False, timeout=120
    )
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.fixture
def generated(tmp_path, config_dict, git_identity):
    plan = build_plan(parse_config(config_dict))
    write_tree(tmp_path, render_plan(plan))
    return plan, tmp_path


def test_lists_and_tests_every_workload(generated):
    plan, root = generated
    for repo in plan.app_repos:
        out = run(root / repo.folder, "sh", "scripts/ci.sh", "workloads").stdout
        assert sorted(line.split()[0] for line in out.splitlines()) == sorted(
            w.name for w in repo.workloads
        )
        env = {**os.environ, "PYTHON": sys.executable}
        run(root / repo.folder, "sh", "scripts/ci.sh", "test", env=env)


def test_failing_tests_fail_the_script(generated):
    plan, root = generated
    repo = plan.app_repos[0]
    wl = repo.workloads[0]
    test_file = root / repo.folder / wl.source_dir / "tests" / "test_main.py"
    broken = (
        "\nclass Broken(unittest.TestCase):\n    def test_fails(self):\n        self.fail('x')\n"
    )
    test_file.write_text(test_file.read_text() + broken)
    env = {**os.environ, "PYTHON": sys.executable}
    result = run(root / repo.folder, "sh", "scripts/ci.sh", "test", env=env, check=False)
    assert result.returncode != 0


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck not installed")
def test_scripts_pass_shellcheck(generated):
    plan, root = generated
    run(root, "shellcheck", "-s", "sh", str(root / plan.app_repos[0].folder / "scripts/ci.sh"))
    run(root, "shellcheck", str(root / plan.gitops.folder / "scripts/bootstrap-local.sh"))


@pytest.fixture
def shipping(generated, tmp_path_factory):
    """An app repo with two commits, a bare GitOps remote and a stub docker on PATH."""
    plan, root = generated
    app = root / plan.app_repos[0].folder
    run(app, "git", "init", "-q", "-b", "main")
    run(app, "git", "add", "-A")
    run(app, "git", "commit", "-q", "-m", "first")
    first = run(app, "git", "rev-parse", "HEAD").stdout.strip()
    run(app, "git", "commit", "-q", "--allow-empty", "-m", "second")
    second = run(app, "git", "rev-parse", "HEAD").stdout.strip()

    remote = tmp_path_factory.mktemp("remote") / "gitops.git"
    run(root, "git", "init", "-q", "--bare", "-b", "main", str(remote))
    gitops = root / plan.gitops.folder
    run(gitops, "git", "init", "-q", "-b", "main")
    run(gitops, "git", "add", "-A")
    run(gitops, "git", "commit", "-q", "-m", "init")
    run(gitops, "git", "push", "-q", str(remote), "main")

    bin_dir = tmp_path_factory.mktemp("bin")
    (bin_dir / "docker").write_text(DOCKER_STUB)
    (bin_dir / "docker").chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "DOCKER_LOG": str(bin_dir / "docker.log"),
        "REGISTRY_USERNAME": "u",
        "REGISTRY_PASSWORD": "p",
        "GITOPS_TOKEN": "t",
        "GITOPS_PUSH_URL": str(remote),
    }

    def ship(commit, check=True, **overrides):
        full = {**env, "COMMIT": commit, **overrides}
        return run(app, "sh", "scripts/ci.sh", "ship", env=full, check=check)

    def released(name):
        path = f"environments/dev/{name}/release.yaml"
        out = run(root, "git", "--git-dir", str(remote), "show", f"main:{path}", check=False)
        return yaml.safe_load(out.stdout) if out.returncode == 0 else None

    return plan, ship, released, first, second, remote


def test_ship_records_a_release_per_workload(shipping):
    plan, ship, released, _, second, _ = shipping
    ship(second)
    for wl in plan.app_repos[0].workloads:
        record = released(wl.name)
        assert record["revision"] == second
        assert record["image"].startswith(f"ghcr.io/acme/atlas-{wl.name}:{second}@sha256:")
        assert record["scorePath"] == wl.score_path


def test_ship_never_rolls_back_a_newer_release(shipping):
    plan, ship, released, first, second, _ = shipping
    ship(second)
    out = ship(first).stdout
    assert "skip" in out
    name = plan.app_repos[0].workloads[0].name
    assert released(name)["revision"] == second


def test_ship_retries_when_the_push_is_rejected(shipping):
    plan, ship, released, _, second, remote = shipping
    hook = remote / "hooks" / "pre-receive"
    hook.write_text(REJECT_FIRST_PUSH)
    hook.chmod(0o755)
    out = ship(second).stdout
    assert "retrying" in out
    assert released(plan.app_repos[0].workloads[0].name)["revision"] == second


def test_ship_fails_fast_without_settings(shipping):
    _, ship, released, _, second, _ = shipping
    result = ship(second, check=False, GITOPS_TOKEN="")
    assert result.returncode != 0
    assert "GITOPS_TOKEN" in result.stderr
    assert released("api") is None
