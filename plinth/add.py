"""`plinth add`: grow an existing project with a new service or worker.

Only files that belong to the new workload are created. Existing files are never
overwritten; ones that plinth would now generate differently are reported so the
user can review them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from plinth import config as defaults
from plinth.loader import ConfigError, config_to_dict, dump_config, load_config, parse_config
from plinth.plan import build_plan
from plinth.render import render_plan
from plinth.schema import AppKind, Architecture, ProjectConfig
from plinth.write import init_repo, write_tree


@dataclass
class AddResult:
    config: ProjectConfig
    created: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    new_repos: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def add_application(
    project_dir: Path, kind: AppKind, name: str, port: int | None = None, init_git: bool = True
) -> AddResult:
    config_path = project_dir / defaults.CONFIG_FILENAME
    old = load_config(config_path)
    data = config_to_dict(old)
    notes = []

    if kind is AppKind.MODULAR_MONOLITH:
        raise ConfigError("a project has exactly one modular-monolith; add a service or worker")
    if old.project.architecture is Architecture.MODULAR_MONOLITH:
        data["project"]["architecture"] = Architecture.HYBRID.value
        notes.append("architecture changed from modular-monolith to hybrid")

    app = {"name": name, "kind": kind.value}
    if port is not None:
        app["port"] = port
    data["applications"].append(app)
    new = parse_config(data, source=str(config_path))

    old_plan, new_plan = build_plan(old), build_plan(new)
    old_folders = {r.folder for r in old_plan.repos}
    files = render_plan(new_plan)
    result = AddResult(config=new, notes=notes)

    new_repos = [r for r in new_plan.repos if r.folder not in old_folders]
    for repo in new_repos:
        if (project_dir / repo.folder).exists():
            raise ConfigError(f"cannot create repository folder, it already exists: {repo.folder}")

    owned = _new_workload_prefixes(new_plan, name)
    to_write = {}
    for rel, content in sorted(files.items()):
        folder = rel.split("/", 1)[0]
        dest = project_dir / rel
        if folder not in old_folders or rel.startswith(owned):
            if dest.exists():
                if dest.read_bytes() != content:
                    result.kept.append(rel)
                continue
            to_write[rel] = content
            result.created.append(rel)
        elif dest.exists() and dest.read_bytes() != content:
            result.kept.append(rel)

    write_tree(project_dir, to_write)
    config_path.write_text(dump_config(new), encoding="utf-8")

    for repo in new_repos:
        result.new_repos.append(repo.folder)
        if init_git:
            warning = init_repo(project_dir / repo.folder, repo.url)
            if warning:
                result.warnings.append(warning)
    return result


def _new_workload_prefixes(plan, name: str) -> tuple[str, ...]:
    prefixes = [
        f"{repo.folder}/{wl.source_dir}"
        for repo, wl in plan.workloads()
        if wl.name == name and wl.source_dir
    ]
    prefixes += [
        f"{plan.gitops.folder}/environments/{env}/{name}/" for env in plan.config.environments
    ]
    return tuple(prefixes)
