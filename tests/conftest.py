from __future__ import annotations

import copy
from pathlib import Path

import pytest

from plinth.model.loader import load_config
from plinth.model.plan import build_plan
from plinth.output.render import render_plan

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = sorted((ROOT / "examples").glob("*/plinth.yaml"))

BASE_CONFIG = {
    "project": {
        "name": "atlas",
        "architecture": "hybrid",
        "layout": "monorepo",
        "gitProvider": "github",
        "gitBaseUrl": "https://github.com/acme",
        "registry": "ghcr.io/acme",
    },
    "applications": [
        {"name": "api", "kind": "modular-monolith"},
        {"name": "worker", "kind": "worker"},
        {"name": "notifier", "kind": "service", "port": 8081},
    ],
    "environments": ["dev", "production"],
}


@pytest.fixture
def config_dict():
    """A fresh, valid config dict; tests mutate it to probe one rule at a time."""
    return copy.deepcopy(BASE_CONFIG)


@pytest.fixture(params=EXAMPLES, ids=lambda p: p.parent.name)
def example(request) -> Path:
    return request.param


@pytest.fixture
def rendered(example):
    """(plan, files) for one example, rendered in memory."""
    plan = build_plan(load_config(example))
    return plan, render_plan(plan)


@pytest.fixture
def git_identity(monkeypatch):
    """A git identity for commits made in tests, independent of the user's config."""
    for key, value in {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
    }.items():
        monkeypatch.setenv(key, value)
