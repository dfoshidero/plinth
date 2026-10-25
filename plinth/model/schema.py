"""Project configuration schema (plinth.yaml)."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from plinth import config as defaults

NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
# https://host[:port]/org[/subgroup...]; no quotes, spaces or template characters
GIT_BASE_URL_RE = re.compile(r"^https://[A-Za-z0-9.-]+(?::[0-9]+)?(?:/[A-Za-z0-9._~-]+)+$")
# host[:port][/path] as Docker image references allow it: lowercase only
REGISTRY_RE = re.compile(
    r"^[a-z0-9]+(?:[.-][a-z0-9]+)*(?::[0-9]+)?(?:/[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*)*$"
)


def _reject_placeholder(value: str, what: str) -> None:
    if defaults.PLACEHOLDER in value:
        raise ValueError(f"{what} still contains the placeholder '{defaults.PLACEHOLDER}...'")


def validate_registry(value: str) -> str:
    _reject_placeholder(value, "registry")
    if not REGISTRY_RE.fullmatch(value):
        raise ValueError(
            "registry must be lowercase host[/path] without scheme or trailing slash, "
            "e.g. ghcr.io/acme"
        )
    return value


def validate_git_base_url(value: str) -> str:
    _reject_placeholder(value, "gitBaseUrl")
    if not GIT_BASE_URL_RE.fullmatch(value):
        raise ValueError(
            "gitBaseUrl must look like https://host/org (no trailing slash), "
            "e.g. https://github.com/acme"
        )
    return value


def validate_name(value: str, what: str) -> str:
    if not NAME_RE.fullmatch(value):
        raise ValueError(
            f"{what} '{value}' must be lowercase kebab-case "
            "(start with a letter; only a-z, 0-9, and single hyphens)"
        )
    if not defaults.NAME_MIN_LEN <= len(value) <= defaults.NAME_MAX_LEN:
        raise ValueError(
            f"{what} '{value}' must be {defaults.NAME_MIN_LEN}-{defaults.NAME_MAX_LEN} characters"
        )
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
    git_base_url: str = Field(alias="gitBaseUrl")
    registry: str

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return validate_name(v, "project.name")

    @field_validator("registry")
    @classmethod
    def _registry(cls, v: str) -> str:
        return validate_registry(v)

    @field_validator("git_base_url")
    @classmethod
    def _git_base_url(cls, v: str) -> str:
        return validate_git_base_url(v)


class ApplicationSpec(StrictModel):
    name: str
    kind: AppKind
    port: int | None = Field(default=None, ge=1, le=65535)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        validate_name(v, "application name")
        if v in defaults.RESERVED_APP_NAMES:
            raise ValueError(f"application name '{v}' is reserved")
        return v

    @model_validator(mode="after")
    def _worker_has_no_port(self) -> ApplicationSpec:
        if self.kind is AppKind.WORKER and self.port is not None:
            raise ValueError(f"application '{self.name}': workers have no HTTP port")
        return self

    @property
    def http_port(self) -> int | None:
        if self.kind is AppKind.WORKER:
            return None
        return self.port if self.port is not None else defaults.DEFAULT_PORT


class ProjectConfig(StrictModel):
    project: ProjectSpec
    applications: list[ApplicationSpec] = Field(min_length=1)
    environments: list[str] = Field(default_factory=lambda: list(defaults.DEFAULT_ENVIRONMENTS))

    @field_validator("environments")
    @classmethod
    def _envs(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("at least one environment is required")
        for e in v:
            validate_name(e, "environment")
        if len(set(v)) != len(v):
            raise ValueError("environment names must be unique")
        if defaults.RELEASE_ENVIRONMENT not in v:
            raise ValueError(
                f"an environment named '{defaults.RELEASE_ENVIRONMENT}' is required (CI releases to it)"
            )
        return v

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
