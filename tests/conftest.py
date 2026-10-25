from __future__ import annotations

import copy
from pathlib import Path

import pytest

from plinth.loader import load_config
from plinth.plan import build_plan
from plinth.render import render_plan

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
