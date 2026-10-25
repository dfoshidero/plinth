"""Properties every generated project must have, whatever the templates look like."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys

import pytest
import yaml

from plinth.loader import parse_config
from plinth.plan import build_plan
from plinth.render import render_plan
from plinth.write import write_tree

SCORE_NAME_RE = r"^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$"


def _is_helm_template(rel: str) -> bool:
    return "/charts/" in rel and "/templates/" in rel


def test_rendering_is_deterministic(example):
    from plinth.loader import load_config

    plan = build_plan(load_config(example))
    assert render_plan(plan) == render_plan(plan)


def test_structured_files_parse(rendered):
    _, files = rendered
    for rel, content in files.items():
        if rel.endswith((".yaml", ".yml")) and not _is_helm_template(rel):
            list(yaml.safe_load_all(content))
        elif rel.endswith(".json"):
            json.loads(content)
        elif rel.endswith(".py"):
            compile(content, rel, "exec")


def test_no_template_syntax_leaks(rendered):
    _, files = rendered
    for rel, content in files.items():
        text = content.decode("utf-8")
        assert "{%" not in text and "{#" not in text, rel


def test_every_repo_has_a_readme_and_metadata(rendered):
    plan, files = rendered
    for repo in plan.repos:
        assert f"{repo.folder}/README.md" in files
        assert f"{repo.folder}/.plinth.yaml" in files


def test_every_workload_has_a_valid_score_file(rendered):
    plan, files = rendered
    for repo, wl in plan.workloads():
        spec = yaml.safe_load(files[f"{repo.folder}/{wl.score_path}"])
        assert spec["apiVersion"] == "score.dev/v1b1"
        assert spec["metadata"]["name"] == wl.name
        assert re.fullmatch(SCORE_NAME_RE, wl.name)
        assert spec["containers"]["main"]["image"]
        has_ports = bool(spec.get("service", {}).get("ports"))
        assert has_ports == (wl.port is not None)


def test_every_workload_has_source_tests_and_dockerfile(rendered):
    plan, files = rendered
    for repo, wl in plan.workloads():
        base = f"{repo.folder}/{wl.source_dir}"
        assert f"{base}Dockerfile" in files
        assert any(k.startswith(f"{base}app/") and k.endswith(".py") for k in files)
        assert any(k.startswith(f"{base}tests/test_") for k in files)


def test_config_values_reach_the_output(rendered):
    plan, files = rendered
    project = plan.config.project
    app_text = b"".join(v for k, v in files.items() if not k.startswith(plan.gitops.folder))
    gitops_text = b"".join(v for k, v in files.items() if k.startswith(plan.gitops.folder))
    assert project.registry.encode() in app_text
    assert plan.gitops.url.encode() in app_text
    assert project.git_base_url.encode() in gitops_text
    for repo in plan.app_repos:
        assert repo.url.encode() in b"".join(
            v for k, v in files.items() if k.startswith(repo.folder + "/")
        )


def test_one_deployment_definition_per_environment(rendered):
    plan, files = rendered
    gitops = plan.gitops.folder
    for env in plan.config.environments:
        docs = [
            yaml.safe_load(v)
            for k, v in files.items()
            if k.startswith(f"{gitops}/apps/") and env.encode() in v
        ]
        assert any(d.get("kind") == "ApplicationSet" for d in docs), env
        for _, wl in plan.workloads():
            assert f"{gitops}/environments/{env}/{wl.name}/values.yaml" in files


@pytest.mark.parametrize(
    ("provider", "expected", "absent"),
    [
        ("github", ".github/workflows/", ".gitlab-ci.yml"),
        ("gitlab", ".gitlab-ci.yml", ".github/"),
        ("generic", None, None),
    ],
)
def test_ci_file_follows_git_provider(config_dict, provider, expected, absent):
    config_dict["project"]["gitProvider"] = provider
    plan = build_plan(parse_config(config_dict))
    files = render_plan(plan)
    for repo in plan.app_repos:
        names = [k[len(repo.folder) + 1 :] for k in files if k.startswith(repo.folder + "/")]
        if expected:
            assert any(n.startswith(expected) for n in names)
            assert not any(n.startswith(absent) for n in names)
        else:
            assert not any(n.startswith((".github/", ".gitlab-ci")) for n in names)


def test_generated_application_tests_pass(rendered, tmp_path):
    plan, files = rendered
    write_tree(tmp_path, files)
    for repo, wl in plan.workloads():
        workdir = tmp_path / repo.folder / wl.source_dir
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, f"{wl.name}:\n{result.stderr}"


@pytest.mark.skipif(shutil.which("helm") is None, reason="helm not installed")
def test_helm_chart_renders_each_workload(rendered, tmp_path):
    plan, files = rendered
    write_tree(tmp_path, files)
    chart = tmp_path / plan.gitops.folder / "charts" / "workload"
    for repo, wl in plan.workloads():
        result = subprocess.run(
            [
                "helm",
                "template",
                wl.name,
                str(chart),
                "-f",
                str(tmp_path / repo.folder / wl.score_path),
                "--set",
                "image=example/image:1",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        kinds = {d["kind"] for d in yaml.safe_load_all(result.stdout) if d}
        assert "Deployment" in kinds
        assert ("Service" in kinds) == (wl.port is not None)
