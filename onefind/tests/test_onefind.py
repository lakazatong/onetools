from onefind.__main__ import main


def make_tree(root, paths):
    for name in paths:
        path = root / name
        path.mkdir(parents=True, exist_ok=True) if name.endswith("/") else None
        if not name.endswith("/"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()


def test_substring_search_matches_files_and_directories(tmp_path, capsys):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "app.toml").touch()
    (tmp_path / "my-config.json").touch()
    (tmp_path / "other.txt").touch()

    assert main(["config", "-d", str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "config",
    ]


def test_wildcard_matches_names_recursively(tmp_path, capsys):
    (tmp_path / "src" / "nested").mkdir(parents=True)
    (tmp_path / "src" / "main.py").touch()
    (tmp_path / "src" / "nested" / "test.py").touch()
    (tmp_path / "README.md").touch()

    assert main(["*.py", "-d", str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "src/main.py",
        "src/nested/test.py",
    ]


def test_queries_are_or_and_case_sensitive(tmp_path, capsys):
    (tmp_path / "Config.toml").touch()
    (tmp_path / "settings.json").touch()

    assert main(["config", "*.json", "-d", str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines() == ["settings.json"]


def test_symlinks_are_not_followed(tmp_path, capsys):
    target = tmp_path / "target"
    target.mkdir()
    (target / "needle.txt").touch()
    (tmp_path / "alias").symlink_to(target, target_is_directory=True)

    assert main(["needle", "-d", str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines() == []
