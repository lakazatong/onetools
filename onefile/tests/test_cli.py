import pytest
from onefile.__main__ import fence_for, main


def write(root, files):
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def run(root, *args, output=None):
    output = output or (root.parent / (root.name + "_out.txt"))
    code = main(["-d", str(root), "-o", str(output), *args])
    return code, output


def test_bundle_format(tmp_path):
    root = tmp_path / "proj"
    write(root, {"a.txt": "hello", "b/c.py": "x = 1\n"})
    code, output = run(root)
    assert code == 0
    assert output.read_text(encoding="utf-8") == (
        "a.txt:\n\n```\nhello\n```\n\nb/c.py:\n\n```\nx = 1\n```\n\n"
    )


def test_patterns_select_files(tmp_path):
    root = tmp_path / "proj"
    write(root, {"src/a.py": "a", "src/b.txt": "b", "docs/c.md": "c"})
    _code, output = run(root, "src", "!src/**/*.txt")
    text = output.read_text(encoding="utf-8")
    assert "src/a.py:" in text
    assert "b.txt" not in text
    assert "docs" not in text


def test_dry_run_lists_posix_paths_and_writes_nothing(tmp_path, capsys):
    root = tmp_path / "proj"
    write(root, {"a.txt": "a", "sub/b.txt": "b"})
    code, output = run(root, "--dry")
    assert code == 0
    assert capsys.readouterr().out.split() == ["a.txt", "sub/b.txt"]
    assert not output.exists()


def test_output_inside_root_is_never_bundled(tmp_path):
    root = tmp_path / "proj"
    write(root, {"a.txt": "a"})
    out = root / "all.txt"
    run(root, output=out)
    first = out.read_text(encoding="utf-8")
    run(root, output=out)
    assert out.read_text(encoding="utf-8") == first
    assert "all.txt" not in first


def test_output_in_a_new_subdirectory(tmp_path):
    root = tmp_path / "proj"
    write(root, {"a.txt": "a"})
    out = root / "build" / "all.txt"
    run(root, output=out)
    first = out.read_text(encoding="utf-8")
    run(root, output=out)
    assert out.read_text(encoding="utf-8") == first
    assert "build" not in first


def test_fence_grows_with_backticks_in_content(tmp_path):
    assert fence_for("no ticks") == "```"
    assert fence_for("``") == "```"
    assert fence_for("```") == "````"
    assert fence_for("a ```` b ``` c") == "`````"

    root = tmp_path / "proj"
    write(root, {"README.md": "```py\nprint(1)\n```\n"})
    _, output = run(root)
    assert output.read_text(encoding="utf-8") == (
        "README.md:\n\n````\n```py\nprint(1)\n```\n````\n\n"
    )


def test_empty_file(tmp_path):
    root = tmp_path / "proj"
    write(root, {"empty.txt": ""})
    _, output = run(root)
    assert output.read_text(encoding="utf-8") == "empty.txt:\n\n```\n```\n\n"


def test_bom_is_dropped_and_crlf_normalized(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "a.txt").write_bytes(b"\xef\xbb\xbfone\r\ntwo\r\n")
    _, output = run(root)
    assert output.read_bytes() == b"a.txt:\n\n```\none\ntwo\n```\n\n"


def test_binary_files_are_skipped(tmp_path):
    root = tmp_path / "proj"
    write(root, {"a.txt": "a"})
    (root / "b.bin").write_bytes(b"\x00\x01")
    _, output = run(root)
    assert "b.bin" not in output.read_text(encoding="utf-8")


def test_header(tmp_path):
    root = tmp_path / "proj"
    write(root, {"a.txt": "a"})
    _code, output = run(root, "--header", "a.txt")
    text = output.read_text(encoding="utf-8")
    assert text.startswith("Generated using: onefile ")
    assert text.split("\n")[1] == f"Under {root.resolve()}"
    assert "a.txt:\n\n```\na\n```" in text


def test_invalid_cli_pattern_exits_cleanly(tmp_path, capsys):
    root = tmp_path / "proj"
    write(root, {"a.txt": "a"})
    with pytest.raises(SystemExit) as info:
        run(root, "../x")
    assert info.value.code == 2
    err = capsys.readouterr().err
    assert "cannot contain '..'" in err
    assert "Traceback" not in err


def test_invalid_filter_file_exits_cleanly_and_writes_nothing(tmp_path, capsys):
    root = tmp_path / "proj"
    write(root, {"a.txt": "a", "onefile_exclude.txt": "fine\nbad!pattern\n"})
    code, output = run(root)
    assert code == 2
    err = capsys.readouterr().err
    assert "onefile_exclude.txt:2" in err
    assert "Traceback" not in err
    assert not output.exists()


def test_missing_root_directory(tmp_path, capsys):
    with pytest.raises(SystemExit) as info:
        main(["-d", str(tmp_path / "nope")])
    assert info.value.code == 2
    assert "not a directory" in capsys.readouterr().err


def test_filter_files_are_never_bundled(tmp_path):
    root = tmp_path / "proj"
    write(
        root,
        {"a.txt": "a", "onefile_include.txt": ".\n", "sub/onefile_exclude.txt": "x\n"},
    )
    _, output = run(root)
    text = output.read_text(encoding="utf-8")
    assert "onefile_include" not in text
    assert "onefile_exclude" not in text
    assert "a.txt:" in text


def test_no_filter_files_uses_only_cli_patterns(tmp_path):
    root = tmp_path / "proj"
    write(
        root,
        {
            "a.py": "a",
            "b.py": "b",
            "onefile_include.txt": "b.py\n",
            "onefile_exclude.txt": "../invalid\n",
        },
    )

    code, output = run(root, "--ignore-files", "a.py")

    assert code == 0
    text = output.read_text(encoding="utf-8")
    assert "a.py:" in text
    assert "b.py:" not in text
    assert "onefile_include.txt" not in text
    assert "onefile_exclude.txt" not in text
