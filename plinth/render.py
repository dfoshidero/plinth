"""Render blueprints into an in-memory file map."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as dist_version
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from plinth import config as defaults
from plinth import settings
from plinth.loader import dump_config
from plinth.plan import Plan, RepoPlan

BLUEPRINTS_DIR = Path(__file__).resolve().parent / "blueprints"
TEMPLATE_SUFFIX = ".j2"
DOT_PREFIX = "dot-"  # blueprint "dot-gitignore" renders as ".gitignore"
EXECUTABLE_SUFFIXES = (".sh",)

try:
    GENERATOR_VERSION = dist_version("plinth-cli")
except PackageNotFoundError:  # running from a bare checkout without install
    GENERATOR_VERSION = "0.0.0+uninstalled"

FileMap = dict[str, bytes]


def make_env(blueprints_root: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(blueprints_root)),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _output_path(rel: str) -> str:
    parts = ["." + p[len(DOT_PREFIX) :] if p.startswith(DOT_PREFIX) else p for p in rel.split("/")]
    out = "/".join(parts)
    return out.removesuffix(TEMPLATE_SUFFIX)


def render_tree(
    env: Environment, blueprints_root: Path, blueprint: str, context: dict, prefix: str
) -> FileMap:
    base = blueprints_root / blueprint
    if not base.is_dir():
        return {}
    out: FileMap = {}
    for src in sorted(p for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        rel = src.relative_to(base).as_posix()
        if rel.endswith(TEMPLATE_SUFFIX):
            content = env.get_template(f"{blueprint}/{rel}").render(**context).encode("utf-8")
        else:
            content = src.read_bytes()
        out[prefix + _output_path(rel)] = content
    return out


def _render_one(env: Environment, template: str, context: dict) -> bytes:
    return env.get_template(template).render(**context).encode("utf-8")


def _metadata(repo: RepoPlan, plan: Plan) -> bytes:
    data = {
        "generator": {"name": "plinth", "version": GENERATOR_VERSION},
        "project": plan.config.project.name,
        "repo": {"folder": repo.folder, "role": repo.role},
    }
    return yaml.safe_dump(data, sort_keys=True).encode("utf-8")


def render_plan(plan: Plan, blueprints_root: Path = BLUEPRINTS_DIR) -> FileMap:
    env = make_env(blueprints_root)
    project = plan.config.project
    base_ctx = {
        "config": plan.config,
        "project": project,
        "plan": plan,
        "defaults": defaults,
        "git_token_user": defaults.GIT_TOKEN_USER[project.git_provider.value],
        "ci_settings": settings.ci_settings(plan),
        "ci_settings_location": settings.SETTINGS_LOCATION[project.git_provider],
        "registry_note": settings.registry_note(plan),
    }
    files: FileMap = {}

    for repo in plan.repos:
        ctx = {**base_ctx, "repo": repo}
        root = f"{repo.folder}/"
        files.update(render_tree(env, blueprints_root, f"repo/{repo.role}", ctx, root))
        files[root + defaults.REPO_METADATA_FILENAME] = _metadata(repo, plan)

        if repo.role == "app":
            for blueprint in ("common", project.git_provider.value):
                files.update(render_tree(env, blueprints_root, f"ci/{blueprint}", ctx, root))
            for wl in repo.workloads:
                wctx = {**ctx, "workload": wl}
                for blueprint in ("workload/common", f"workload/{wl.kind.value}"):
                    files.update(
                        render_tree(env, blueprints_root, blueprint, wctx, root + wl.source_dir)
                    )
        else:
            files[root + defaults.CONFIG_FILENAME] = dump_config(plan.config).encode("utf-8")
            for environment in plan.config.environments:
                ectx = {**ctx, "environment": environment}
                files[f"{root}apps/{environment}.yaml"] = _render_one(
                    env, "gitops/applicationset.yaml.j2", ectx
                )
                for app_repo, wl in plan.workloads():
                    wctx = {**ectx, "workload": wl, "app_repo": app_repo}
                    files[f"{root}environments/{environment}/{wl.name}/values.yaml"] = _render_one(
                        env, "gitops/values.yaml.j2", wctx
                    )

    return files


def config_path(plan: Plan) -> str:
    """Where the project's config lives in the rendered output."""
    return f"{plan.gitops.folder}/{defaults.CONFIG_FILENAME}"


def is_executable(rel: str) -> bool:
    return rel.endswith(EXECUTABLE_SUFFIXES)
