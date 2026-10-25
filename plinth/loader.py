"""Load, validate and serialise plinth.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from plinth.schema import ProjectConfig


class ConfigError(Exception):
    """Raised for any user-facing configuration problem."""


def parse_config(data: Any, source: str = "<config>") -> ProjectConfig:
    if not isinstance(data, dict):
        raise ConfigError(f"{source}: top level must be a mapping")
    try:
        return ProjectConfig.model_validate(data)
    except ValidationError as exc:
        lines = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err["loc"]) or "<root>"
            msg = err["msg"].removeprefix("Value error, ")
            lines.append(f"  {loc}: {msg}")
        raise ConfigError(f"{source}: invalid configuration\n" + "\n".join(lines)) from None


def load_config(path: Path) -> ProjectConfig:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc.strerror}") from None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: YAML parse error: {exc}") from None
    return parse_config(data, source=str(path))


def config_to_dict(config: ProjectConfig) -> dict:
    return config.model_dump(mode="json", by_alias=True, exclude_none=True)


def dump_config(config: ProjectConfig) -> str:
    return yaml.safe_dump(config_to_dict(config), sort_keys=False)
