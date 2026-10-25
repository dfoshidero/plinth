"""Command line entry point: `plinth ...` or `python -m plinth ...`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import questionary
import yaml

from plinth import config as defaults
from plinth.add import add_application
from plinth.loader import ConfigError, dump_config, load_config, parse_config
from plinth.plan import Plan, build_plan
from plinth.render import GENERATOR_VERSION, FileMap, render_plan
from plinth.schema import AppKind
from plinth.wizard import run_wizard
from plinth.write import OutputExistsError, write_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plinth")
    parser.add_argument("--version", action="version", version=f"plinth {GENERATOR_VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    project = sub.add_parser("project", help="interactive setup: answer questions, then generate")
    project.add_argument(
        "--output",
        type=Path,
        default=Path("."),
        help="parent folder; <output>/<project>/ is created",
    )
    project.add_argument("--no-git", action="store_true", help="skip git init and first commit")

    validate = sub.add_parser("validate", help="validate a config without writing files")
    validate.add_argument("--config", required=True, type=Path)

    generate = sub.add_parser("generate", help="generate local repository folders from a config")
    generate.add_argument("--config", required=True, type=Path)
    generate.add_argument("--output", required=True, type=Path)
    generate.add_argument("--dry-run", action="store_true", help="list files, write nothing")
    generate.add_argument("--no-git", action="store_true", help="skip git init and first commit")

    add = sub.add_parser("add", help="add a service or worker to a generated project")
    add.add_argument("kind", choices=[AppKind.SERVICE.value, AppKind.WORKER.value])
    add.add_argument("name")
    add.add_argument("--port", type=int, help="HTTP port (services only)")
    add.add_argument(
        "--project-dir",
        type=Path,
        default=Path("."),
        help=f"folder containing {defaults.CONFIG_FILENAME} (default: current)",
    )
    add.add_argument("--no-git", action="store_true", help="skip git init for new repositories")
    return parser


def _summary(plan: Plan, files: FileMap) -> list[str]:
    lines = []
    for repo in plan.repos:
        count = sum(1 for k in files if k.startswith(repo.folder + "/"))
        lines.append(f"  {repo.folder}/  ({repo.role}, {count} files)")
    return lines


def _generate(plan: Plan, target: Path, init_git: bool) -> int:
    files = render_plan(plan)
    files[defaults.CONFIG_FILENAME] = dump_config(plan.config).encode("utf-8")
    try:
        warnings = write_project(target, files, {r.folder: r.url for r in plan.repos}, init_git)
    except OutputExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print(f"generated {len(files)} files under {target}")
    return 0


def save_answers(directory: Path, text: str) -> Path:
    """Save wizard answers without overwriting anything already there."""
    stem, suffix = Path(defaults.CONFIG_FILENAME).stem, Path(defaults.CONFIG_FILENAME).suffix
    for n in range(1000):
        path = directory / (f"{stem}{suffix}" if n == 0 else f"{stem}-{n}{suffix}")
        try:
            with path.open("x", encoding="utf-8") as fh:
                fh.write(text)
            return path
        except FileExistsError:
            continue
    raise OSError(f"could not find a free file name for answers in {directory}")


def run_project(output: Path, init_git: bool) -> int:
    try:
        answers = run_wizard()
    except KeyboardInterrupt:
        print("\naborted, nothing written", file=sys.stderr)
        return 130

    try:
        config = parse_config(answers, source="your answers")
    except ConfigError as exc:
        saved = save_answers(Path.cwd(), yaml.safe_dump(answers, sort_keys=False))
        print(f"error: {exc}", file=sys.stderr)
        print(
            f"answers saved to {saved}; edit it and run: "
            f"plinth generate --config {saved.name} --output {output}",
            file=sys.stderr,
        )
        return 2

    plan = build_plan(config)
    target = output / config.project.name
    print(f"\nWill create under {target.resolve()}:")
    print("\n".join(_summary(plan, render_plan(plan))))
    if not questionary.confirm("Generate now?", default=True).unsafe_ask():
        print("nothing written")
        return 0
    return _generate(plan, target, init_git)


def run_add(args: argparse.Namespace) -> int:
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
    for folder in result.new_repos:
        print(f"new repository: {folder}/ (create it on your git host and push)")
    touched = sorted({p.split("/", 1)[0] for p in result.created} - set(result.new_repos))
    if touched:
        print(f"commit the new files in: {', '.join(touched)}")
    if result.kept:
        print("\nkept as-is (plinth would now generate these differently; review by hand):")
        for path in result.kept:
            print(f"  {path}")
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "project":
        return run_project(args.output, init_git=not args.no_git)
    if args.command == "add":
        return run_add(args)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    plan = build_plan(config)
    if args.command == "validate":
        folders = ", ".join(r.folder for r in plan.repos)
        print(
            f"ok: {config.project.name} ({config.project.architecture}, "
            f"{config.project.layout}) -> {folders}"
        )
        return 0

    target = args.output / config.project.name
    if args.dry_run:
        files = render_plan(plan)
        for rel in sorted(files):
            print(target / rel)
        print(f"dry run: {len(files)} files, nothing written", file=sys.stderr)
        if target.exists():
            print(
                f"error: {target} already exists; generate would refuse to write", file=sys.stderr
            )
            return 3
        return 0
    return _generate(plan, target, init_git=not args.no_git)
