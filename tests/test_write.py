import shutil
import subprocess

import pytest

from plinth.write import OutputExistsError, init_repo, write_project, write_tree


def test_write_project_creates_files(tmp_path):
    target = tmp_path / "proj"
    write_project(target, {"a/x.txt": b"x", "b/run.sh": b"#!/bin/sh\n"}, {}, init_git=False)
    assert (target / "a" / "x.txt").read_bytes() == b"x"
    assert (target / "b" / "run.sh").stat().st_mode & 0o111


def test_write_project_refuses_existing_target(tmp_path):
    target = tmp_path / "proj"
    target.mkdir()
    with pytest.raises(OutputExistsError):
        write_project(target, {"x.txt": b"x"}, {}, init_git=False)


def test_failed_write_leaves_nothing_behind(tmp_path, monkeypatch):
    def boom(root, files):
        (root / "partial.txt").write_text("half")
        raise RuntimeError("disk full")

    monkeypatch.setattr("plinth.write.write_tree", boom)
    with pytest.raises(RuntimeError):
        write_project(tmp_path / "proj", {"x.txt": b"x"}, {}, init_git=False)
    assert list(tmp_path.iterdir()) == []


def test_write_tree_creates_nested_dirs(tmp_path):
    write_tree(tmp_path, {"deep/er/file.txt": b"ok"})
    assert (tmp_path / "deep" / "er" / "file.txt").read_text() == "ok"


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_init_repo_commits_and_sets_remote(tmp_path, monkeypatch):
    for key, value in {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }.items():
        monkeypatch.setenv(key, value)
    (tmp_path / "file.txt").write_text("hi")
    assert init_repo(tmp_path, "https://example.com/acme/repo.git") is None

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=tmp_path, capture_output=True, text=True, check=False
        ).stdout

    assert git("rev-list", "--count", "HEAD").strip() == "1"
    assert git("remote", "get-url", "origin").strip() == "https://example.com/acme/repo.git"
    assert git("status", "--porcelain") == ""
