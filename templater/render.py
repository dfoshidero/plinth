"""Render blueprints into an in-memory file map, then write it once."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as dist_version
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from templater.plan import Plan, RepoPlan

TEMPLATE_SUFFIX = ".j2"
METADATA_FILE = ".template-metadata.yaml"

try:
    GENERATOR_VERSION = dist_version("universal-project-template")
except PackageNotFoundError:  # running from a bare checkout without install
    GENERATOR_VERSION = "0.0.0+uninstalled"

FileMap = dict[str, bytes]


class OutputExistsError(Exception):
    pass


def make_env(blueprints_root: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(blueprints_root)),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    
def render_tree(
    env: Environment, blueprints_root: Path, blueprint: str, context: dict, prefix: str
) -> FileMap:
    base = blueprints_root / blueprint
    if not base.is_dir():
        raise FileNotFoundError(f"blueprint directory missing: {base}")
    out: FileMap = {}
    for src in sorted(p for p in base.rglob("*") if p.is_file()):
        rel = src.relative_to(base).as_posix()
        if rel.endswith(TEMPLATE_SUFFIX):
            content = env.get_template(f"{blueprint}/{rel}").render(**context).encode("utf-8")
            rel = rel[: -len(TEMPLATE_SUFFIX)]
        else:
            content = src.read_bytes()
        out[prefix + rel] = content
    return out

def _metadata(plan: Plan, repo: RepoPlan) -> bytes:
    data = {
        "generator": {"name": "universal-project-template", "version": GENERATOR_VERSION},
        "configDigest": plan.config_digest,
        "project": plan.config.project.name,
        "architecture": plan.config.project.architecture.value,
        "layout": plan.config.project.layout.value,
        "repo": {"folder": repo.folder, "role": repo.role},
    }
    return yaml.safe_dump(data, sort_keys=True).encode("utf-8")


def render_plan(plan: Plan, blueprints_root: Path) -> FileMap:
    env = make_env(blueprints_root)
    base_ctx = {"config": plan.config, "project": plan.config.project, "plan": plan}
    files: FileMap = {}

    for repo in plan.repos:
        ctx = {**base_ctx, "repo": repo}
        root = f"{repo.folder}/"
        files.update(render_tree(env, blueprints_root, f"repo/{repo.role}", ctx, root))

        for wl in repo.workloads:
            wctx = {**ctx, "workload": wl}
            files.update(
                render_tree(env, blueprints_root, f"apps/{wl.kind}", wctx, root + wl.source_dir)
            )
            workload_yaml = env.get_template("workload/workload.yaml.j2").render(**wctx)
            files[f"{root}workloads/{wl.name}.yaml"] = workload_yaml.encode("utf-8")

        files[root + METADATA_FILE] = _metadata(plan, repo)

    return files


def write_files(root: Path, files: FileMap) -> None:
    if root.exists():
        raise OutputExistsError(f"refusing to write into existing path: {root}")
    for rel in sorted(files):
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(files[rel])