import pytest

from plinth.loader import parse_config
from plinth.plan import build_plan


@pytest.fixture
def plan_for(config_dict):
    def make(layout):
        config_dict["project"]["layout"] = layout
        return build_plan(parse_config(config_dict))

    return make


def test_monorepo_has_one_app_repo_holding_every_workload(plan_for):
    plan = plan_for("monorepo")
    assert len(plan.app_repos) == 1
    assert {w.name for _, w in plan.workloads()} == {"api", "worker", "notifier"}
    assert all(w.source_dir for _, w in plan.workloads())


def test_split_repo_has_one_repo_per_workload(plan_for):
    plan = plan_for("split-repo")
    assert len(plan.app_repos) == 3
    assert all(len(r.workloads) == 1 for r in plan.app_repos)
    assert all(w.source_dir == "" for _, w in plan.workloads())


@pytest.mark.parametrize("layout", ["monorepo", "split-repo"])
def test_always_exactly_one_gitops_repo(plan_for, layout):
    plan = plan_for(layout)
    assert [r.role for r in plan.repos].count("gitops") == 1


@pytest.mark.parametrize("layout", ["monorepo", "split-repo"])
def test_repo_folders_are_unique_and_prefixed(plan_for, layout):
    plan = plan_for(layout)
    folders = [r.folder for r in plan.repos]
    assert len(folders) == len(set(folders))
    assert all(f.startswith("atlas-") for f in folders)


def test_repo_urls_live_under_git_base_url(plan_for):
    plan = plan_for("split-repo")
    for repo in plan.repos:
        assert repo.url == f"https://github.com/acme/{repo.folder}.git"


def test_plan_is_deterministic(config_dict):
    config = parse_config(config_dict)
    assert build_plan(config) == build_plan(config)
