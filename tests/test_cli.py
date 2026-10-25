import subprocess
import sys

import yaml

from plinth.cli import main, save_answers
from tests.conftest import EXAMPLES


def _write_config(tmp_path, config_dict):
    path = tmp_path / "plinth.yaml"
    path.write_text(yaml.safe_dump(config_dict))
    return path


def test_validate_ok(capsys):
    assert main(["validate", "--config", str(EXAMPLES[0])]) == 0
    assert capsys.readouterr().out.startswith("ok:")


def test_validate_reports_bad_config(tmp_path, config_dict, capsys):
    config_dict["project"]["name"] = "Bad"
    assert main(["validate", "--config", str(_write_config(tmp_path, config_dict))]) == 2
    assert "project.name" in capsys.readouterr().err


def test_validate_missing_file(tmp_path, capsys):
    assert main(["validate", "--config", str(tmp_path / "nope.yaml")]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_generate_writes_project_and_config(tmp_path, config_dict):
    path = _write_config(tmp_path, config_dict)
    out = tmp_path / "out"
    assert main(["generate", "--config", str(path), "--output", str(out), "--no-git"]) == 0
    assert (out / "atlas" / "atlas-gitops" / "plinth.yaml").exists()
    assert not (out / "atlas" / "plinth.yaml").exists()


def test_generate_lists_what_to_set_up(tmp_path, config_dict, capsys):
    config_dict["project"]["registry"] = "registry.example.com/acme"
    path = _write_config(tmp_path, config_dict)
    main(["generate", "--config", str(path), "--output", str(tmp_path / "out"), "--no-git"])
    out = capsys.readouterr().out
    assert "Next steps" in out
    for name in ("GITOPS_TOKEN", "REGISTRY_USERNAME", "REGISTRY_PASSWORD"):
        assert name in out
    assert "https://github.com/acme/atlas-gitops.git" in out


def test_generate_refuses_existing_target(tmp_path, config_dict):
    path = _write_config(tmp_path, config_dict)
    (tmp_path / "out" / "atlas").mkdir(parents=True)
    assert (
        main(["generate", "--config", str(path), "--output", str(tmp_path / "out"), "--no-git"])
        == 3
    )


def test_dry_run_writes_nothing(tmp_path, config_dict, capsys):
    path = _write_config(tmp_path, config_dict)
    out = tmp_path / "out"
    assert main(["generate", "--config", str(path), "--output", str(out), "--dry-run"]) == 0
    assert not out.exists()
    assert "nothing written" in capsys.readouterr().err


def test_dry_run_warns_when_target_exists(tmp_path, config_dict, capsys):
    path = _write_config(tmp_path, config_dict)
    (tmp_path / "out" / "atlas").mkdir(parents=True)
    assert (
        main(["generate", "--config", str(path), "--output", str(tmp_path / "out"), "--dry-run"])
        == 3
    )
    assert "already exists" in capsys.readouterr().err


def test_add_command(tmp_path, config_dict, capsys):
    path = _write_config(tmp_path, config_dict)
    out = tmp_path / "out"
    main(["generate", "--config", str(path), "--output", str(out), "--no-git"])
    capsys.readouterr()
    code = main(["add", "service", "billing", "--project-dir", str(out / "atlas"), "--no-git"])
    assert code == 0
    assert "created" in capsys.readouterr().out


def test_update_command_reports_errors(tmp_path, capsys):
    assert main(["update", "--project-dir", str(tmp_path)]) == 2
    assert "no plinth project" in capsys.readouterr().err


def test_add_command_reports_errors(tmp_path, capsys):
    assert main(["add", "service", "billing", "--project-dir", str(tmp_path), "--no-git"]) == 2
    assert "error" in capsys.readouterr().err


def test_save_answers_never_overwrites(tmp_path):
    existing = tmp_path / "plinth.yaml"
    existing.write_text("keep me")
    first = save_answers(tmp_path, "a")
    second = save_answers(tmp_path, "b")
    assert existing.read_text() == "keep me"
    assert first != existing and second != first
    assert first.read_text() == "a" and second.read_text() == "b"


def test_module_entry_point():
    result = subprocess.run(
        [sys.executable, "-m", "plinth", "--version"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert result.stdout.startswith("plinth ")
