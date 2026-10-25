"""Project configuration schema (template.project.yaml)"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
MAX_NAME_LEN = 30
RESERVED_APP_NAMES = frozenset(("app", "gitops"))


def validate_name(value: str, what: str) -> str:
    if not NAME_RE.fullmatch(value):
        raise ValueError(
                f"{what} '{value}' must be lowercase kebab-case"
                "(start with a letter; only a-z, 0-9, and single hyphens)"
            )
    if len(value) > MAX_NAME_LEN:
        raise ValueError(f"{what} '{value}' is longer than {MAX_NAME_LEN} characters")
    return value


class Architecture(StrEnum):
    MODULAR_MONOLITH = "modular-monolith"
    MICROSERVICES = "microservices"
    HYBRID = "hybrid"


class Layout(StrEnum):
    MONOREPO = "monorepo"
    SPLIT_REPO = "split-repo"


class GitProvider(StrEnum):
    GITHUB = "github"
    GITLAB = "gitlab"
    GENERIC = "generic"


class AppKind(StrEnum):
    MODULAR_MONOLITH = "modular-monolith"
    SERVICE = "service"
    WORKER = "worker"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class ProjectSpec(StrictModel):
    name: str
    architecture: Architecture
    layout: Layout
    git_provider: GitProvider = Field(alias="gitProvider")
    registry: str

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return validate_name(v, "project.name")

    @field_validator("registry")
    @classmethod
    def _registry(cls, v: str) -> str:
        if "://" in v or v.endswith("/"):
            raise ValueError("registry must be host[/path] without scheme or trailing slash")
        return v


class ApplicationSpec(StrictModel):
    name: str
    kind: AppKind
    port: int = Field(default=8000, ge=1, le=65535)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        validate_name(v, "application name")
        if v in RESERVED_APP_NAMES:
            raise ValueError(f"application name '{v}' is reserved")
        return v


class CISpec(StrictModel):
    engine: str = "dagger"

    @field_validator("engine")
    @classmethod
    def _engine(cls, v: str) -> str:
        if v != "dagger":
            raise ValueError("ci.engine must be 'dagger'")
        return v


class CDSpec(StrictModel):
    controller: str = "argocd"
    environments: list[str] = Field(default_factory=lambda: ["dev", "production"])

    @field_validator("controller")
    @classmethod
    def _controller(cls, v: str) -> str:
        if v != "argocd":
            raise ValueError("cd.controller must be 'argocd'")
        return v

    @field_validator("environments")
    @classmethod
    def _envs(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("at least one environment is required")
        for e in v:
            validate_name(e, "environment")
        if len(set(v)) != len(v):
            raise ValueError("environment names must be unique")
        if "dev" not in v:
            raise ValueError("an environment named 'dev' is required (CI targets it)")
        return v


class ProjectConfig(StrictModel):
    project: ProjectSpec
    applications: list[ApplicationSpec] = Field(min_length=1)
    ci: CISpec = Field(default_factory=CISpec)
    cd: CDSpec = Field(default_factory=CDSpec)

    @model_validator(mode="after")
    def _architecture_rules(self) -> ProjectConfig:
        names = [a.name for a in self.applications]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ValueError(f"duplicate application names: {dupes}")

        monoliths = [a for a in self.applications if a.kind is AppKind.MODULAR_MONOLITH]
        others = [a for a in self.applications if a.kind is not AppKind.MODULAR_MONOLITH]
        arch = self.project.architecture

        if arch is Architecture.MODULAR_MONOLITH and (len(monoliths) != 1 or others):
            raise ValueError(
                "architecture 'modular-monolith' requires exactly one application "
                "of kind 'modular-monolith' and no others"
            )
        if arch is Architecture.MICROSERVICES and monoliths:
            raise ValueError(
                "architecture 'microservices' must not contain kind 'modular-monolith'"
            )
        if arch is Architecture.HYBRID and (len(monoliths) != 1 or not others):
            raise ValueError(
                "architecture 'hybrid' requires exactly one 'modular-monolith' "
                "plus at least one 'service' or 'worker'"
            )
        return self













