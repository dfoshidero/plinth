"""Command line entry point: `plinth ...` or `python -m plinth ...`.

Each command lives in plinth/commands/; this file only parses arguments and dispatches.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from plinth.commands import add, generate, project, update
from plinth.model.schema import AppKind
from plinth.output.render import GENERATOR_VERSION

PROJECT_DIR_HELP = (
    "folder holding the project's repositories, or any one of them (default: current)"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plinth")
    parser.add_argument("--version", action="version", version=f"plinth {GENERATOR_VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    cmd = sub.add_parser("project", help="interactive setup: answer questions, then generate")
    cmd.add_argument(
        "--output",
        type=Path,
        default=Path("."),
        help="parent folder; <output>/<project>/ is created",
    )
    cmd.add_argument("--no-git", action="store_true", help="skip git init and first commit")
    cmd.set_defaults(run=project.run)

    cmd = sub.add_parser("validate", help="validate a config without writing files")
    cmd.add_argument("--config", required=True, type=Path)
    cmd.set_defaults(run=generate.run_validate)

    cmd = sub.add_parser("generate", help="generate local repository folders from a config")
    cmd.add_argument("--config", required=True, type=Path)
    cmd.add_argument("--output", required=True, type=Path)
    cmd.add_argument("--dry-run", action="store_true", help="list files, write nothing")
    cmd.add_argument("--no-git", action="store_true", help="skip git init and first commit")
    cmd.set_defaults(run=generate.run_generate)

    cmd = sub.add_parser("add", help="add a service or worker to a generated project")
    cmd.add_argument("kind", choices=[AppKind.SERVICE.value, AppKind.WORKER.value])
    cmd.add_argument("name")
    cmd.add_argument("--port", type=int, help="HTTP port (services only)")
    cmd.add_argument("--project-dir", type=Path, default=Path("."), help=PROJECT_DIR_HELP)
    cmd.add_argument("--no-git", action="store_true", help="skip git init for new repositories")
    cmd.set_defaults(run=add.run)

    cmd = sub.add_parser("update", help="merge the latest plinth templates into every repository")
    cmd.add_argument("--project-dir", type=Path, default=Path("."), help=PROJECT_DIR_HELP)
    cmd.set_defaults(run=update.run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.run(args)
