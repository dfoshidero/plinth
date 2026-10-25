"""Find a generated project on disk: the folder holding its repositories and its config.

The config (plinth.yaml) lives in the GitOps repository so it is versioned and shared.
Commands work from the folder holding the repositories or from inside any of them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from plinth import config as defaults
from plinth.loader import ConfigError, parse_config
from plinth.schema import ProjectConfig


@dataclass(frozen=True)
class Workspace:
    root: Path  # folder holding the repository folders
    config_path: Path
    legacy: bool = False  # config sits in root, as written by plinth 0.2


def _role(repo_dir: Path) -> str | None:
    try:
        data = yaml.safe_load((repo_dir / defaults.REPO_METADATA_FILENAME).read_text())
        return data["repo"]["role"]
    except (OSError, yaml.YAMLError, KeyError, TypeError):
        return None


def find_workspace(start: Path) -> Workspace:
    start = start.resolve()
    if _role(start) is not None:  # inside one of the repositories
        start = start.parent

    found = (
        [
            d / defaults.CONFIG_FILENAME
            for d in sorted(p for p in start.iterdir() if p.is_dir())
            if _role(d) == "gitops" and (d / defaults.CONFIG_FILENAME).is_file()
        ]
        if start.is_dir()
        else []
    )
    if len(found) == 1:
        return Workspace(start, found[0])
    if len(found) > 1:
        names = ", ".join(p.parent.name for p in found)
        raise ConfigError(f"{start} holds several plinth projects ({names}); run from one of them")

    legacy = start / defaults.CONFIG_FILENAME
    if legacy.is_file():
        return Workspace(start, legacy, legacy=True)
    raise ConfigError(
        f"no plinth project found in {start}: run from the folder holding the repositories, "
        f"with the GitOps repository (which contains {defaults.CONFIG_FILENAME}) cloned there"
    )


def load_project_config(workspace: Workspace) -> ProjectConfig:
    path = workspace.config_path
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc.strerror}") from None
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: YAML parse error: {exc}") from None
    return parse_config(data, source=str(path))
