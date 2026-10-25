"""`plinth add`: grow an existing project with a new service or worker.

Only files that belong to the new workload are created. Existing files are never
overwritten; ones that plinth would now generate differently are reported so the
user can review them (or merge them with `plinth update`).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

from plinth.model.loader import ConfigError, config_to_dict, dump_config, parse_config
from plinth.model.plan import Plan, RepoPlan, build_plan
from plinth.model.schema import AppKind, Architecture, ProjectConfig
from plinth.model.workspace import find_workspace, load_project_config
from plinth.output.checklist import next_steps
from plinth.output.render import config_path, render_plan
from plinth.output.write import init_repo, write_tree


@dataclass
class AddResult:
    config: ProjectConfig
    plan: Plan
    root: Path
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    new_repos: list[RepoPlan] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def add_application(
    project_dir: Path, kind: AppKind, name: str, port: int | None = None, init_git: bool = True
) -> AddResult:
    workspace = find_workspace(project_dir)
    root = workspace.root
    old, notes = load_project_config(workspace), []
    data = config_to_dict(old)

    if kind is AppKind.MODULAR_MONOLITH:
        raise ConfigError("a project has exactly one modular-monolith; add a service or worker")
    if old.project.architecture is Architecture.MODULAR_MONOLITH:
        data["project"]["architecture"] = Architecture.HYBRID.value
        notes.append("architecture changed from modular-monolith to hybrid")

    app = {"name": name, "kind": kind.value}
    if port is not None:
        app["port"] = port
    data["applications"].append(app)
    new = parse_config(data, source=str(workspace.config_path))

    old_plan, new_plan = build_plan(old), build_plan(new)
    old_folders = {r.folder for r in old_plan.repos}
    files = render_plan(new_plan)
    config_rel = config_path(new_plan)
    result = AddResult(config=new, plan=new_plan, root=root, notes=notes)

    new_repos = [r for r in new_plan.repos if r.folder not in old_folders]
    for repo in new_repos:
        if (root / repo.folder).exists():
            raise ConfigError(f"cannot create repository folder, it already exists: {repo.folder}")

    owned = _new_workload_prefixes(new_plan, name)
    to_write = {}
    for rel, content in sorted(files.items()):
        if rel == config_rel:
            continue
        folder = rel.split("/", 1)[0]
        dest = root / rel
        if folder not in old_folders or rel.startswith(owned):
            if dest.exists():
                if dest.read_bytes() != content:
                    result.kept.append(rel)
                continue
            to_write[rel] = content
            result.created.append(rel)
        elif dest.exists() and dest.read_bytes() != content:
            result.kept.append(rel)

    missing = sorted(
        {rel.split("/", 1)[0] for rel in to_write}
        & old_folders - {p.name for p in root.iterdir() if p.is_dir()}
    )
    if missing:
        raise ConfigError(
            f"repositories not found in {root}: {', '.join(missing)}; "
            "clone them next to the GitOps repository first"
        )

    write_tree(root, to_write)
    (root / config_rel).write_text(dump_config(new), encoding="utf-8")
    result.updated.append(config_rel)
    if workspace.legacy:
        workspace.config_path.unlink()
        notes.append(f"moved {workspace.config_path.name} into {config_rel} so it is versioned")

    for repo in new_repos:
        result.new_repos.append(repo)
        if init_git:
            warning = init_repo(root / repo.folder, repo.url)
            if warning:
                result.warnings.append(warning)
    return result


def _new_workload_prefixes(plan: Plan, name: str) -> tuple[str, ...]:
    prefixes = [
        f"{repo.folder}/{wl.source_dir}"
        for repo, wl in plan.workloads()
        if wl.name == name and wl.source_dir
    ]
    prefixes += [
        f"{plan.gitops.folder}/environments/{env}/{name}/" for env in plan.config.environments
    ]
    return tuple(prefixes)


def run(args: argparse.Namespace) -> int:
    try:
        result = add_application(
            args.project_dir, AppKind(args.kind), args.name, args.port, init_git=not args.no_git
        )
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for note in result.notes:
        print(f"note: {note}")
    for path in result.created:
        print(f"created  {path}")
    new_folders = {r.folder for r in result.new_repos}
    touched = sorted({p.split("/", 1)[0] for p in result.created + result.updated} - new_folders)
    if touched:
        print(f"commit the new files in: {', '.join(touched)}")
    if result.kept:
        print("\nkept as-is (plinth would now generate these differently; review by hand):")
        for path in result.kept:
            print(f"  {path}")
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if result.new_repos:
        git_ready = not args.no_git and not result.warnings
        print("\n".join(next_steps(result.plan, result.root, result.new_repos, git_ready)))
    return 0
