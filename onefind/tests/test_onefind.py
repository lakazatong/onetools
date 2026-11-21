from onefind.__main__ import main


def test_literal_only_checks_current_directory(tmp_path, capsys):
    (tmp_path / "hermes").mkdir()
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "hermes").touch()

    assert main(["hermes", "-d", str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines() == ["hermes"]


def test_literal_path_resolves_each_component(tmp_path, capsys):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "file.txt").touch()
    (tmp_path / "other" / "a" / "b").mkdir(parents=True)

    assert main(["a/b", "-d", str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines() == ["a/b"]


def test_wildcard_only_enumerates_matching_component(tmp_path, capsys):
    (tmp_path / "src-one").mkdir()
    (tmp_path / "src-two").mkdir()
    (tmp_path / "other").mkdir()
    (tmp_path / "src-one" / "main.py").touch()
    (tmp_path / "src-two" / "main.txt").touch()

    assert main(["src-*/main.*", "-d", str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines() == ["src-one/main.py", "src-two/main.txt"]


def test_globstar_recurses_from_its_position(tmp_path, capsys):
    (tmp_path / "src" / "one" / "deep").mkdir(parents=True)
    (tmp_path / "unrelated" / "deep").mkdir(parents=True)
    (tmp_path / "src" / "test.py").touch()
    (tmp_path / "src" / "one" / "test.py").touch()
    (tmp_path / "src" / "one" / "deep" / "test.py").touch()
    (tmp_path / "unrelated" / "test.py").touch()

    assert main(["src/**/test.py", "-d", str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "src/one/deep/test.py",
        "src/one/test.py",
        "src/test.py",
    ]


def test_terminal_globstar_lists_descendants(tmp_path, capsys):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "file.txt").touch()
    (tmp_path / "a" / "b" / "deep.txt").touch()

    assert main(["a/**", "-d", str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "a/b",
        "a/b/deep.txt",
        "a/file.txt",
    ]


def test_patterns_are_deduplicated_and_negation_excludes(tmp_path, capsys):
    (tmp_path / "a.txt").touch()
    (tmp_path / "b.txt").touch()

    assert main(["*.txt", "a.txt", "!a.txt", "-d", str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines() == ["b.txt"]


def test_symlinks_are_not_followed(tmp_path, capsys):
    target = tmp_path / "target"
    target.mkdir()
    (target / "needle.txt").touch()
    (tmp_path / "alias").symlink_to(target, target_is_directory=True)

    assert main(["**/needle.txt", "-d", str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines() == ["target/needle.txt"]


def test_invalid_pattern_exits_cleanly(tmp_path, capsys):
    try:
        main(["../outside", "-d", str(tmp_path)])
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError("expected argparse error")
    assert "cannot contain '..'" in capsys.readouterr().err
