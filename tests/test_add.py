import pytest
import yaml

from plinth.add import add_application
from plinth.loader import ConfigError, load_config, parse_config
from plinth.plan import build_plan
from plinth.render import render_plan
from plinth.schema import AppKind, Architecture
from plinth.write import write_project


@pytest.fixture
def project(tmp_path, config_dict):
    def make(layout="monorepo", architecture="hybrid", applications=None):
        config_dict["project"]["layout"] = layout
        config_dict["project"]["architecture"] = architecture
        if applications is not None:
            config_dict["applications"] = applications
        config = parse_config(config_dict)
        files = render_plan(build_plan(config))
        files["plinth.yaml"] = yaml.safe_dump(config_dict).encode()
        root = tmp_path / "atlas"
        write_project(root, files, {}, init_git=False)
        return root

    return make


def test_add_service_to_monorepo_creates_its_files(project):
    root = project()
    result = add_application(root, AppKind.SERVICE, "billing", port=8090, init_git=False)
    assert (root / "atlas-app" / "apps" / "billing" / "score.yaml").exists()
    assert any("environments/dev/billing/" in p for p in result.created)
    assert result.new_repos == []
    names = [a.name for a in load_config(root / "plinth.yaml").applications]
    assert "billing" in names


def test_add_to_split_repo_creates_a_new_repository(project):
    root = project(layout="split-repo")
    result = add_application(root, AppKind.WORKER, "mailer", init_git=False)
    assert result.new_repos == ["atlas-mailer"]
    assert (root / "atlas-mailer" / "score.yaml").exists()


def test_add_grows_modular_monolith_into_hybrid(project):
    root = project(
        architecture="modular-monolith", applications=[{"name": "api", "kind": "modular-monolith"}]
    )
    result = add_application(root, AppKind.WORKER, "mailer", init_git=False)
    assert result.config.project.architecture is Architecture.HYBRID
    assert result.notes


def test_add_never_overwrites_existing_files(project):
    root = project()
    readme = root / "atlas-app" / "README.md"
    readme.write_text("my own words")
    result = add_application(root, AppKind.SERVICE, "billing", init_git=False)
    assert readme.read_text() == "my own words"
    assert "atlas-app/README.md" in result.kept


def test_add_does_not_resurrect_deleted_files(project):
    root = project()
    script = root / "atlas-gitops" / "scripts" / "bootstrap-local.sh"
    script.unlink()
    add_application(root, AppKind.SERVICE, "billing", init_git=False)
    assert not script.exists()


def test_add_rejects_duplicate_name(project):
    root = project()
    with pytest.raises(ConfigError, match="duplicate"):
        add_application(root, AppKind.SERVICE, "worker", init_git=False)


def test_add_rejects_second_monolith(project):
    root = project()
    with pytest.raises(ConfigError):
        add_application(root, AppKind.MODULAR_MONOLITH, "core", init_git=False)


def test_add_rejects_port_on_worker(project):
    root = project()
    with pytest.raises(ConfigError, match="no HTTP port"):
        add_application(root, AppKind.WORKER, "mailer", port=9000, init_git=False)


def test_add_requires_a_project_config(tmp_path):
    with pytest.raises(ConfigError, match="cannot read"):
        add_application(tmp_path, AppKind.SERVICE, "billing", init_git=False)
