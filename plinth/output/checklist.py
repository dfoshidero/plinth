"""What a user has to set up after generating: CI secrets and variables, pushes, cluster access.

One source for the terminal checklist and the generated READMEs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from plinth import config as defaults
from plinth.model.plan import Plan, RepoPlan
from plinth.model.schema import GitProvider

SETTINGS_LOCATION = {
    GitProvider.GITHUB: "Settings > Secrets and variables > Actions",
    GitProvider.GITLAB: "Settings > CI/CD > Variables",
    GitProvider.GENERIC: "your CI system's environment variables",
}

GITOPS_TOKEN_HINT = {
    GitProvider.GITHUB: "fine-grained token with Contents: read and write on {repo}",
    GitProvider.GITLAB: "project access token with write_repository on {repo}",
    GitProvider.GENERIC: "token that can push to {repo}",
}


@dataclass(frozen=True)
class CiSetting:
    kind: str  # how the provider calls it: secret, variable, masked variable, env
    name: str
    purpose: str


def _kinds(provider: GitProvider) -> tuple[str, str]:
    """(kind for a secret value, kind for a plain value)."""
    if provider is GitProvider.GITHUB:
        return "secret", "variable"
    if provider is GitProvider.GITLAB:
        return "masked variable", "variable"
    return "env", "env"


def builtin_registry(plan: Plan) -> bool:
    """True when CI logs in to the registry with the provider's own job credentials."""
    provider = plan.config.project.git_provider
    host = plan.config.project.registry.split("/", 1)[0]
    return defaults.BUILTIN_REGISTRY.get(provider.value) == host


def registry_note(plan: Plan) -> str | None:
    if not builtin_registry(plan):
        return None
    if plan.config.project.git_provider is GitProvider.GITHUB:
        return (
            "registry: nothing to set; CI logs in to ghcr.io with GITHUB_TOKEN "
            f"(the owner in {plan.config.project.registry} must own the repository)"
        )
    return "registry: nothing to set; CI logs in with GitLab's built-in job credentials"


def ci_settings(plan: Plan) -> list[CiSetting]:
    project = plan.config.project
    provider = project.git_provider
    secret, plain = _kinds(provider)
    gitops = plan.gitops.folder
    settings = [CiSetting(secret, "GITOPS_TOKEN", GITOPS_TOKEN_HINT[provider].format(repo=gitops))]
    if not builtin_registry(plan):
        host = project.registry.split("/", 1)[0]
        settings += [
            CiSetting(plain, "REGISTRY_USERNAME", f"user that can push to {host}"),
            CiSetting(secret, "REGISTRY_PASSWORD", f"password or token for {host}"),
        ]
    return settings


def _pad(rows: list[tuple[str, str, str]]) -> list[str]:
    w0 = max(len(r[0]) for r in rows)
    w1 = max(len(r[1]) for r in rows)
    return [f"{a:<{w0}}  {b:<{w1}}  {c}" for a, b, c in rows]


def next_steps(plan: Plan, root: Path, repos: list[RepoPlan], git_ready: bool) -> list[str]:
    """Checklist printed after generate/add for `repos`, which live under `root`."""
    project = plan.config.project
    provider = project.git_provider
    lines = ["", "Next steps", ""]
    n = 1

    if repos:
        host = provider.value if provider is not GitProvider.GENERIC else "your git host"
        lines.append(f"{n}. Create these empty repositories on {host} (no README or license):")
        lines += [f"     {r.url}" for r in repos]
        ordered = sorted(repos, key=lambda r: r.role != "gitops")
        if git_ready:
            lines.append("   then push each one, the GitOps repository first:")
            lines += [
                f"     (cd {root / r.folder} && git push -u origin main {defaults.TEMPLATE_BRANCH})"
                for r in ordered
            ]
        else:
            lines.append("   then make each folder a git repository with that remote and push it.")
        lines.append("")
        n += 1

    app_repos = [r for r in repos if r.role == "app"]
    if app_repos:
        names = ", ".join(r.folder for r in app_repos)
        lines.append(f"{n}. Set these CI settings in {names}")
        lines.append(f"   ({SETTINGS_LOCATION[provider]}); CI cannot release without them:")
        rows = [(s.kind, s.name, s.purpose) for s in ci_settings(plan)]
        lines += ["     " + row for row in _pad(rows)]
        note = registry_note(plan)
        if note:
            lines.append(f"     {note}")
        if provider is GitProvider.GENERIC:
            lines.append("   then run `scripts/ci.sh test` and `scripts/ci.sh ship` from your CI.")
        lines.append("")
        n += 1

    if any(r.role == "gitops" for r in repos):
        script = root / plan.gitops.folder / "scripts" / "bootstrap-local.sh"
        lines.append(f"{n}. Deploy to a local cluster once CI has shipped: {script}")
        lines.append("   If the repositories are private, set GIT_USERNAME and GIT_TOKEN.")
        lines.append("   If the images are private, set REGISTRY_USERNAME and REGISTRY_PASSWORD.")
        lines.append("")

    lines.append("Each repository's README.md repeats these steps.")
    return lines
