from collections import deque

import pytest

from plinth import wizard
from plinth.loader import parse_config


class _Prompt:
    def __init__(self, answer):
        self.answer = answer

    def unsafe_ask(self):
        return self.answer


@pytest.fixture
def scripted(monkeypatch):
    """Feed the wizard a fixed list of answers, in question order."""

    def run(answers):
        queue = deque(answers)
        ask = lambda *args, **kwargs: _Prompt(queue.popleft())
        monkeypatch.setattr(wizard.questionary, "text", ask)
        monkeypatch.setattr(wizard.questionary, "select", ask)
        monkeypatch.setattr(wizard.questionary, "print", lambda *a, **k: None)
        result = wizard.run_wizard()
        assert not queue, "wizard asked fewer questions than scripted"
        return result

    return run


def test_hybrid_answers_make_a_valid_config(scripted):
    answers = scripted(
        [
            "atlas",
            "hybrid",
            "split-repo",
            "gitlab",
            "https://gitlab.com/acme",
            "registry.example.com/acme",
            "api",
            "8080",  # monolith
            "mailer",
            "worker",  # a worker: no port question
            "billing",
            "service",
            "8090",
            "",  # finish
            "dev,staging,production",
        ]
    )
    config = parse_config(answers)
    assert [a.name for a in config.applications] == ["api", "mailer", "billing"]
    assert config.environments == ["dev", "staging", "production"]


def test_monolith_answers_make_a_valid_config(scripted):
    answers = scripted(
        [
            "atlas",
            "modular-monolith",
            "monorepo",
            "github",
            "https://github.com/acme",
            "ghcr.io/acme",
            "api",
            "8000",
            "dev,production",
        ]
    )
    assert len(parse_config(answers).applications) == 1
