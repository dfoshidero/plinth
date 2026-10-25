"""Turn a validated config into a deterministic generation plan."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from templater.config import AppKind, Layout, ProjectConfig

RepoRole = Literal["app", "gitops"]


@dataclass(frozen=True)
class WorkloadPlan:
    name: str
    kind: AppKind
    port: int
    source_dir: str # "" at repo root, or "apps/<name>/" in a monorepo

    @property
    def dockerfile(self) -> str:
        return f"{self.source_dir}Dockerfile"


@dataclass(frozen=True)
class RepoPlan:
    folder: str
    role: RepoRole
    workloads: tuple[WorkloadPlan, ...]


@dataclass(frozen=True)
class Plan:
    config: ProjectConfig
    repos: tuple[RepoPlan, ...]
    config_digest: str


def config_digest(config: ProjectConfig) -> str:
    canonical = config.model_dump_json(by_alias=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_plan(config: ProjectConfig) -> Plan:
    project = config.project
    repos: list[RepoPlan] = []

    if project.layout is Layout.MONOREPO:
        workloads = tuple(
            WorkloadPlan(a.name, a.kind, a.port, f"apps/{a.name}/") for a in config.applications
        )
        repos.append(RepoPlan(f"{project.name}-app", "app", workloads))
    else:
        for a in config.applications:
            workload = WorkloadPlan(a.name, a.kind, a.port, "")
            repos.append(RepoPlan(f"{project.name}-{a.name}", "app", (workload,)))

    repos.append(RepoPlan(f"{project.name}-gitops", "gitops", ()))
    return Plan(config=config, repos=tuple(repos), config_digest=config_digest(config))
