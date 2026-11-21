import os

import pytest
from onefile.__main__ import iter_project_files
from onefile.walker import is_text_file

from onepatterns import PatternError, normalize_pattern


def make_pattern(priority, pattern):
    return (priority, *normalize_pattern(pattern))


def make_tree(root, paths):
    for path in paths:
        path = root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")


def check(tmp_path, patterns, cases, filter_files=None):
    make_tree(tmp_path, cases)

    for name, content in (filter_files or {}).items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    matcher = [make_pattern(1, pattern) for pattern in patterns]

    always_exclude = {"onefile_include.txt", "onefile_exclude.txt"}

    result = {
        path.relative_to(tmp_path).as_posix()
        for path in iter_project_files(
            tmp_path,
            matcher,
            always_exclude,
        )
    }

    expected = {path for path, included in cases.items() if included}

    assert result == expected


def test_cli_generic_include_does_not_override_specific_file_exclude(tmp_path):
    check(
        tmp_path,
        ["**/*.py", "!.venv"],
        {
            ".venv/foo.py": False,
            "foo.py": True,
        },
    )


def test_cli_specific_include_overrides_file_exclude(tmp_path):
    check(
        tmp_path,
        [".venv/foo.py"],
        {
            ".venv/foo.py": True,
        },
        filter_files={"onefile_exclude.txt": ".venv\n"},
    )


def test_specific_file_exclude_overrides_generic_include(tmp_path):
    check(
        tmp_path,
        ["src/**"],
        {
            "src/__init__.py": False,
        },
        filter_files={"onefile_exclude.txt": "**/__init__.py\n"},
    )


def test_egg_info_excluded_from_src_glob(tmp_path):
    check(
        tmp_path,
        ["src/**"],
        {
            "src/mypackage/dead/beef.py": True,
            "src/mypackage/foo.py": True,
            "src/mypackage.egg-info/PKG-INFO": False,
        },
        filter_files={"onefile_exclude.txt": "**/*.egg-info\n"},
    )


def test_cli_wins_same_specificity(tmp_path):
    check(
        tmp_path,
        ["src/foo.py"],
        {
            "src/foo.py": True,
        },
        filter_files={"onefile_exclude.txt": "src/foo.py\n"},
    )


def test_single_folder_not_recursive(tmp_path):
    check(
        tmp_path,
        ["src"],
        {
            "src/foo.py": True,
            "src/common/base.py": True,
            "other/hello.txt": False,
        },
    )

    check(
        tmp_path,
        ["src/*"],
        {
            "src/foo.py": True,
            "src/common/base.py": False,
            "other/hello.txt": False,
        },
    )


def test_root_star_not_recursive(tmp_path):
    check(
        tmp_path,
        ["*"],
        {
            "src/foo.txt": False,
            "base.py": True,
        },
    )

    check(
        tmp_path,
        ["!*"],
        {
            "src/foo.txt": True,
            "base.py": False,
        },
    )


def test_real_case(tmp_path):
    # In an exclude file a "!" line is a *positive* pattern, and any positive
    # pattern turns "everything" into a whitelist. The first line, "!.", is
    # the whitelist of everything; the rest trims it down.
    check(
        tmp_path,
        [],
        {
            "src/main.jsx": True,
            "index.html": True,
            "vite.config.js": True,
            "package.json": False,
            "README.md": False,
            "src/assets/logo.svg": False,
            "node_modules/react/index.js": False,
            ".build/out.js": False,
            ".vscode/settings.json": False,
            "desktop/main.c": True,
            "desktop/external/lib.c": False,
            "mobile/android/gradlew": False,
            "mobile/android/gradlew.bat": False,
            "mobile/android/gradle/wrapper/gradle-wrapper.properties": False,
            "mobile/android/.gradle/cache.bin": False,
            "mobile/android/.kotlin/session.log": False,
            "mobile/android/app/build/outputs/app.apk": False,
            "mobile/android/app/build.gradle": True,
            "mobile/android/app/src/main/res/layout/main.xml": False,
            "mobile/android/app/src/main/java/App.kt": True,
        },
        filter_files={
            "onefile_exclude.txt": """!.
.build
.vscode
desktop/external
mobile/android/.gradle
mobile/android/.kotlin
mobile/android/app/build
mobile/android/app/src/main/res
mobile/android/gradle
mobile/android/gradlew
mobile/android/gradlew.bat
node_modules
src/assets
*
!index.html
!vite.config.js"""
        },
    )


def test_exclude_file_without_a_positive_pattern_keeps_everything_else(tmp_path):
    check(
        tmp_path,
        [],
        {
            "a.py": True,
            "src/b.py": True,
            "build/c.o": False,
            "src/build/d.o": True,
        },
        filter_files={"onefile_exclude.txt": "build\n"},
    )


def test_include_file_is_a_whitelist(tmp_path):
    check(
        tmp_path,
        [],
        {
            "src/a.py": True,
            "docs/b.md": False,
            "c.txt": False,
        },
        filter_files={"onefile_include.txt": "src\n"},
    )


def test_nested_filter_files_are_relative_to_their_directory(tmp_path):
    check(
        tmp_path,
        [],
        {
            "secret/a.txt": True,
            "sub/secret/b.txt": False,
            "sub/other/c.txt": True,
            "sub/deeper/secret/d.txt": True,
        },
        filter_files={"sub/onefile_exclude.txt": "secret\n"},
    )


def test_nested_include_file_whitelists_its_own_directory_only(tmp_path):
    check(
        tmp_path,
        [],
        {
            "root.txt": True,
            "sub/keep.txt": True,
            "sub/other.txt": False,
        },
        filter_files={"sub/onefile_include.txt": "keep.txt\n"},
    )


def test_deeper_filter_file_beats_a_shallower_one(tmp_path):
    check(
        tmp_path,
        [],
        {
            "a/x.log": False,
            "a/b/x.log": True,
            "a/b/y.log": False,
        },
        filter_files={
            "onefile_exclude.txt": "**/*.log\n",
            "a/b/onefile_include.txt": "x.log\n",
        },
    )


def test_filter_files_are_never_yielded(tmp_path):
    check(
        tmp_path,
        ["."],
        {"a.txt": True},
        filter_files={
            "onefile_include.txt": ".\n",
            "sub/onefile_exclude.txt": "nothing\n",
        },
    )


def test_filter_files_cannot_be_asked_for_explicitly(tmp_path):
    check(
        tmp_path,
        ["sub/onefile_exclude.txt", "a.txt"],
        {"sub/onefile_exclude.txt": False, "a.txt": True},
    )


def test_invalid_filter_file_raises_with_location(tmp_path):
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "onefile_exclude.txt").write_text("ok\n../bad\n")
    with pytest.raises(PatternError, match=r"onefile_exclude\.txt:2"):
        list(iter_project_files(tmp_path, []))


def test_exclude_paths_are_never_yielded(tmp_path):
    make_tree(tmp_path, ["out/all.txt", "a.txt", "sub/all.txt"])
    found = {
        p.relative_to(tmp_path).as_posix()
        for p in iter_project_files(
            tmp_path, [], exclude_paths=[tmp_path / "out" / "all.txt"]
        )
    }
    assert found == {"a.txt", "sub/all.txt"}


def test_always_exclude_by_name(tmp_path):
    make_tree(tmp_path, ["a.txt", "sub/a.txt", "b.txt"])
    found = {
        p.relative_to(tmp_path).as_posix()
        for p in iter_project_files(tmp_path, [], {"a.txt"})
    }
    assert found == {"b.txt"}


def test_binary_and_non_utf8_files_are_skipped(tmp_path):
    (tmp_path / "text.txt").write_text("héllo", encoding="utf-8")
    (tmp_path / "nul.bin").write_bytes(b"abc\x00def")
    (tmp_path / "latin1.txt").write_bytes("héllo".encode("latin-1"))
    (tmp_path / "empty.txt").write_text("")
    found = {p.name for p in iter_project_files(tmp_path, [])}
    assert found == {"text.txt", "empty.txt"}


def test_symlinks_are_not_followed(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "a.txt").write_text("a")
    (tmp_path / "file.txt").write_text("f")
    try:
        os.symlink(real, tmp_path / "dirlink", target_is_directory=True)
        os.symlink(tmp_path / "file.txt", tmp_path / "filelink.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available")
    found = {
        p.relative_to(tmp_path).as_posix() for p in iter_project_files(tmp_path, [])
    }
    assert found == {"real/a.txt", "file.txt"}


def test_symlink_loop_does_not_hang(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    try:
        os.symlink(tmp_path, tmp_path / "loop", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available")
    found = {
        p.relative_to(tmp_path).as_posix() for p in iter_project_files(tmp_path, [])
    }
    assert found == {"a.txt"}


def test_output_is_sorted_by_name(tmp_path):
    make_tree(tmp_path, ["b.txt", "a/z.txt", "a/b.txt", "c/d.txt"])
    found = [
        p.relative_to(tmp_path).as_posix() for p in iter_project_files(tmp_path, [])
    ]
    assert found == ["a/b.txt", "a/z.txt", "b.txt", "c/d.txt"]


# ---- is_text_file ----


def test_is_text_file(tmp_path):
    def write(name, data):
        path = tmp_path / name
        path.write_bytes(data)
        return path

    assert is_text_file(write("empty", b""))
    assert is_text_file(write("ascii", b"hello\n"))
    assert is_text_file(write("bom", b"\xef\xbb\xbfhello"))
    assert not is_text_file(write("nul.bin", b"a\x00b"))
    assert not is_text_file(write("bad", b"\xff\xfe"))
    assert not is_text_file(tmp_path / "missing")


def test_is_text_file_multibyte_character_cut_by_the_probe(tmp_path):
    # 'é' is two bytes and straddles the 8192 byte probe boundary
    path = tmp_path / "boundary.txt"
    path.write_bytes(b"a" * 8191 + "é".encode() + b"tail")
    assert is_text_file(path)

    # but a truncated character at the end of a small file is invalid
    small = tmp_path / "small.txt"
    small.write_bytes(b"abc" + "é".encode()[:1])
    assert not is_text_file(small)
