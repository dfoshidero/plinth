"""Command line entry point: `scaffold ...` or `python -m templater ...`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import questionary
import yaml

from templater.loader import ConfigError, load_config, parse_config
from templater.plan import build_plan
from templater.render import OutputExistsError, render_plan, write_files
from templater.wizard import run_wizard

BLUEPRINTS_DIR = Path(__file__).resolve().parent / "blueprints"
CONFIG_FILENAME = "template.project.yaml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scaffold")
    sub = parser.add_subparsers(dest="command", required=True)

    project = sub.add_parser("project", help="interactive setup: answer questions, then generate")
    project.add_argument("--output", type=Path, default=Path("."),
                         help="parent folder; <output>/<project>/ is created")

    validate = sub.add_parser("validate", help="validate a config without writing files")
    validate.add_argument("--config", required=True, type=Path)

    generate = sub.add_parser("generate", help="generate local repository folders from a config")
    generate.add_argument("--config", required=True, type=Path)
    generate.add_argument("--output", required=True, type=Path)
    generate.add_argument("--dry-run", action="store_true", help="list files, write nothing")
    return parser


def run_project(output: Path) -> int:
    try:
        answers = run_wizard()
    except KeyboardInterrupt:
        print("\naborted, nothing written", file=sys.stderr)
        return 130

    config_text = yaml.safe_dump(answers, sort_keys=False)
    try:
        config = parse_config(answers, source="your answers")
    except ConfigError as exc:
        fallback = Path.cwd() / CONFIG_FILENAME
        fallback.write_text(config_text, encoding="utf-8")
        print(f"error: {exc}", file=sys.stderr)
        print(f"answers saved to {fallback}; edit it and run: "
              f"scaffold generate --config {fallback.name} --output {output}", file=sys.stderr)
        return 2

    plan = build_plan(config)
    files = render_plan(plan, BLUEPRINTS_DIR)
    target = output / config.project.name

    print(f"\nWill create under {target.resolve()}:")
    for repo in plan.repos:
        count = sum(1 for k in files if k.startswith(repo.folder + "/"))
        print(f"  {repo.folder}/  ({repo.role}, {count} files)")
    if not questionary.confirm("Generate now?", default=True).unsafe_ask():
        print("nothing written")
        return 0

    try:
        write_files(target, files)
    except OutputExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    (target / CONFIG_FILENAME).write_text(config_text, encoding="utf-8")
    print(f"generated {len(files)} files under {target}")
    print(f"config saved to {target / CONFIG_FILENAME}; re-run with "
          f"'scaffold generate --config ...' to regenerate into a new folder")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "project":
        return run_project(args.output)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    plan = build_plan(config)
    if args.command == "validate":
        folders = ", ".join(r.folder for r in plan.repos)
        print(f"ok: {config.project.name} ({config.project.architecture}, "
              f"{config.project.layout}) -> {folders}")
        return 0

    files = render_plan(plan, BLUEPRINTS_DIR)
    target = args.output / config.project.name
    if args.dry_run:
        for rel in sorted(files):
            print(target / rel)
        print(f"dry run: {len(files)} files, nothing written", file=sys.stderr)
        return 0

    try:
        write_files(target, files)
    except OutputExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    print(f"generated {len(files)} files under {target}")
    return 0
