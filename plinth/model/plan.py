"""Turn a validated config into a deterministic generation plan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from plinth.model.schema import AppKind, Layout, ProjectConfig

RepoRole = Literal["app", "gitops"]


@dataclass(frozen=True)
class WorkloadPlan:
    name: str
    kind: AppKind
    port: int | None  # None for workers
    source_dir: str  # "" at repo root, or "apps/<name>/" in a monorepo

    @property
    def score_path(self) -> str:
        return f"{self.source_dir}score.yaml"


@dataclass(frozen=True)
class RepoPlan:
    folder: str
    role: RepoRole
    url: str
    workloads: tuple[WorkloadPlan, ...]

    @property
    def web_url(self) -> str:
        return self.url.removesuffix(".git")


@dataclass(frozen=True)
class Plan:
    config: ProjectConfig
    repos: tuple[RepoPlan, ...]

    @property
    def gitops(self) -> RepoPlan:
        return next(r for r in self.repos if r.role == "gitops")

    @property
    def app_repos(self) -> tuple[RepoPlan, ...]:
        return tuple(r for r in self.repos if r.role == "app")

    def workloads(self) -> list[tuple[RepoPlan, WorkloadPlan]]:
        return [(r, w) for r in self.app_repos for w in r.workloads]


def build_plan(config: ProjectConfig) -> Plan:
    project = config.project
    base = project.git_base_url

    def repo(folder: str, role: RepoRole, workloads: tuple[WorkloadPlan, ...]) -> RepoPlan:
        return RepoPlan(folder, role, f"{base}/{folder}.git", workloads)

    repos: list[RepoPlan] = []
    if project.layout is Layout.MONOREPO:
        workloads = tuple(
            WorkloadPlan(a.name, a.kind, a.http_port, f"apps/{a.name}/")
            for a in config.applications
        )
        repos.append(repo(f"{project.name}-app", "app", workloads))
    else:
        for a in config.applications:
            workload = WorkloadPlan(a.name, a.kind, a.http_port, "")
            repos.append(repo(f"{project.name}-{a.name}", "app", (workload,)))

    repos.append(repo(f"{project.name}-gitops", "gitops", ()))
    return Plan(config=config, repos=tuple(repos))
