"""`plinth validate` and `plinth generate`: check a config, then write its repositories."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from plinth.model.loader import ConfigError, load_config
from plinth.model.plan import Plan, build_plan
from plinth.output.checklist import next_steps
from plinth.output.render import FileMap, render_plan
from plinth.output.write import OutputExistsError, write_project


def summary(plan: Plan, files: FileMap) -> list[str]:
    lines = []
    for repo in plan.repos:
        count = sum(1 for k in files if k.startswith(repo.folder + "/"))
        lines.append(f"  {repo.folder}/  ({repo.role}, {count} files)")
    return lines


def write_and_report(plan: Plan, target: Path, init_git: bool) -> int:
    """Write the project, then print what the user has to set up next."""
    files = render_plan(plan)
    try:
        warnings = write_project(target, files, {r.folder: r.url for r in plan.repos}, init_git)
    except OutputExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print(f"generated {len(files)} files under {target}")
    git_ready = init_git and not warnings
    print("\n".join(next_steps(plan, target, list(plan.repos), git_ready)))
    return 0


def _load(path: Path) -> Plan | None:
    try:
        return build_plan(load_config(path))
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return None


def run_validate(args: argparse.Namespace) -> int:
    plan = _load(args.config)
    if plan is None:
        return 2
    project = plan.config.project
    folders = ", ".join(r.folder for r in plan.repos)
    print(f"ok: {project.name} ({project.architecture}, {project.layout}) -> {folders}")
    return 0


def run_generate(args: argparse.Namespace) -> int:
    plan = _load(args.config)
    if plan is None:
        return 2
    target = args.output / plan.config.project.name
    if not args.dry_run:
        return write_and_report(plan, target, init_git=not args.no_git)

    files = render_plan(plan)
    for rel in sorted(files):
        print(target / rel)
    print(f"dry run: {len(files)} files, nothing written", file=sys.stderr)
    if target.exists():
        print(f"error: {target} already exists; generate would refuse to write", file=sys.stderr)
        return 3
    return 0
