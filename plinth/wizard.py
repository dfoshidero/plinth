"""Interactive questions for `plinth project`. Produces a config dict only."""

from __future__ import annotations

import questionary
from questionary import Choice

from plinth import config as defaults
from plinth.schema import NAME_RE, AppKind, Architecture, GitProvider, Layout


def _name_ok(value: str) -> bool | str:
    if NAME_RE.fullmatch(value) and defaults.NAME_MIN_LEN <= len(value) <= defaults.NAME_MAX_LEN:
        return True
    return (
        f"lowercase kebab-case, {defaults.NAME_MIN_LEN}-{defaults.NAME_MAX_LEN} chars, e.g. atlas"
    )


def _port_ok(value: str) -> bool | str:
    return True if value.isdigit() and 0 < int(value) < 65536 else "port must be 1-65535"


def _ask_port(question: str) -> int:
    answer = questionary.text(question, default=str(defaults.DEFAULT_PORT), validate=_port_ok)
    return int(answer.unsafe_ask())


def _ask_applications(architecture: str) -> list[dict]:
    apps: list[dict] = []
    if architecture in (Architecture.MODULAR_MONOLITH, Architecture.HYBRID):
        name = questionary.text(
            "Monolith application name:", default="api", validate=_name_ok
        ).unsafe_ask()
        apps.append(
            {
                "name": name,
                "kind": AppKind.MODULAR_MONOLITH.value,
                "port": _ask_port("Monolith HTTP port:"),
            }
        )
        if architecture == Architecture.MODULAR_MONOLITH:
            return apps

    while True:
        name = questionary.text(
            "Service or worker name (leave empty to finish):",
            validate=lambda v: True if v == "" else _name_ok(v),
        ).unsafe_ask()
        if name == "":
            if any(a["kind"] != AppKind.MODULAR_MONOLITH for a in apps):
                return apps
            questionary.print("At least one service or worker is required.", style="bold")
            continue
        kind = questionary.select(
            f"Kind of '{name}':",
            choices=[
                Choice("service  (HTTP, gets a port and health check)", AppKind.SERVICE.value),
                Choice("worker   (no HTTP port)", AppKind.WORKER.value),
            ],
        ).unsafe_ask()
        app = {"name": name, "kind": kind}
        if kind == AppKind.SERVICE:
            app["port"] = _ask_port("Port:")
        apps.append(app)


def run_wizard() -> dict:
    name = questionary.text("Project name:", validate=_name_ok).unsafe_ask()

    architecture = questionary.select(
        "Application architecture:",
        choices=[
            Choice(
                "modular-monolith  (one process, one image, internal modules)",
                Architecture.MODULAR_MONOLITH.value,
            ),
            Choice(
                "microservices     (several independently built apps)",
                Architecture.MICROSERVICES.value,
            ),
            Choice(
                "hybrid            (one monolith plus independent services/workers)",
                Architecture.HYBRID.value,
            ),
        ],
    ).unsafe_ask()

    layout = questionary.select(
        "Repository layout:",
        choices=[
            Choice("monorepo    (all apps in <project>-app)", Layout.MONOREPO.value),
            Choice("split-repo  (one repo per app)", Layout.SPLIT_REPO.value),
        ],
    ).unsafe_ask()

    provider = questionary.select(
        "Git provider (decides which CI file is generated):",
        choices=[Choice(p.value, p.value) for p in GitProvider],
    ).unsafe_ask()

    git_base_url = questionary.text(
        "Git base URL the repos will live under (https://host/org):",
        default=defaults.DEFAULT_GIT_BASE_URL[provider],
    ).unsafe_ask()

    registry = questionary.text(
        "Container registry (host/path, no scheme):", default=defaults.DEFAULT_REGISTRY
    ).unsafe_ask()

    applications = _ask_applications(architecture)

    envs = questionary.text(
        f"Environments (comma separated, must include {defaults.RELEASE_ENVIRONMENT}):",
        default=",".join(defaults.DEFAULT_ENVIRONMENTS),
    ).unsafe_ask()

    return {
        "project": {
            "name": name,
            "architecture": architecture,
            "layout": layout,
            "gitProvider": provider,
            "gitBaseUrl": git_base_url,
            "registry": registry,
        },
        "applications": applications,
        "environments": [e.strip() for e in envs.split(",") if e.strip()],
    }
