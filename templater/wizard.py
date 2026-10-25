"""Interactive questions for `scaffold project`. Produces a config dict only."""

from __future__ import annotations

import questionary
from questionary import Choice

from templater.config import NAME_RE, AppKind, Architecture, GitProvider, Layout


def _name_ok(value: str) -> bool | str:
    return True if NAME_RE.fullmatch(value) else "lowercase kebab-case, e.g. atlas or billing-api"


def _port_ok(value: str) -> bool | str:
    return True if value.isdigit() and 0 < int(value) < 65536 else "port must be 1-65535"


def _ask_applications(architecture: str) -> list[dict]:
    apps: list[dict] = []
    if architecture in (Architecture.MODULAR_MONOLITH, Architecture.HYBRID):
        name = questionary.text(
            "Monolith application name:", default="api", validate=_name_ok
        ).unsafe_ask()
        port = questionary.text("Monolith HTTP port:", default="8080", validate=_port_ok).unsafe_ask()
        apps.append({"name": name, "kind": AppKind.MODULAR_MONOLITH.value, "port": int(port)})
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
            app["port"] = int(questionary.text("Port:", default="8080", validate=_port_ok).unsafe_ask())
        apps.append(app)


def run_wizard() -> dict:
    name = questionary.text("Project name:", validate=_name_ok).unsafe_ask()

    architecture = questionary.select(
        "Application architecture:",
        choices=[
            Choice("modular-monolith  (one process, one image, internal modules)",
                   Architecture.MODULAR_MONOLITH.value),
            Choice("microservices     (several independently built apps)",
                   Architecture.MICROSERVICES.value),
            Choice("hybrid            (one monolith plus independent services/workers)",
                   Architecture.HYBRID.value),
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
        "CI provider adapter:",
        choices=[Choice(p.value, p.value) for p in GitProvider],
    ).unsafe_ask()

    registry = questionary.text(
        "Container registry (host/path, no scheme):", default="ghcr.io/YOUR_ACCOUNT"
    ).unsafe_ask()

    applications = _ask_applications(architecture)

    envs = questionary.text(
        "Environments (comma separated, must include dev):", default="dev,production"
    ).unsafe_ask()

    return {
        "project": {
            "name": name,
            "architecture": architecture,
            "layout": layout,
            "gitProvider": provider,
            "registry": registry,
        },
        "applications": applications,
        "ci": {"engine": "dagger"},
        "cd": {
            "controller": "argocd",
            "environments": [e.strip() for e in envs.split(",") if e.strip()],
        },
    }

