import pytest

from onepatterns import PatternError, load_patterns, normalize_pattern


def test_normalization_basic():
    assert normalize_pattern("src") == (False, ("src",))
    assert normalize_pattern("./src/") == (False, ("src",))
    assert normalize_pattern("/src") == (False, ("src",))
    assert normalize_pattern("!./src/") == (True, ("src",))

    with pytest.raises(ValueError):
        normalize_pattern("./!src")


def test_dot_and_slash_as_starstar():
    for pattern in (".", "./", ".///", "////", "/./", ".//./"):
        assert normalize_pattern(pattern) == (False, ("**",))

    for pattern in ("!.", "!./", "!.///"):
        assert normalize_pattern(pattern) == (True, ("**",))


def test_double_dot_rejected():
    for pattern in ("../src", "src/../file", "!../../", ".."):
        with pytest.raises(ValueError, match="cannot contain '..'"):
            normalize_pattern(pattern)


def test_triple_dot_is_literal():
    assert normalize_pattern("...") == (False, ("...",))
    assert normalize_pattern("src/.../file") == (False, ("src", "...", "file"))


def test_dot_components_dropped_anywhere():
    assert normalize_pattern("././src") == (False, ("src",))
    assert normalize_pattern("src/./x/.") == (False, ("src", "x"))
    assert normalize_pattern("!./src/./x") == (True, ("src", "x"))


def test_repeated_slashes_collapse():
    assert normalize_pattern("a//b///c") == (False, ("a", "b", "c"))


def test_bang_only_allowed_first():
    for pattern in ("!!src", "src!", "a/!b", "hello!.txt", "!hello!.txt", "./!src"):
        with pytest.raises(PatternError, match="'!'"):
            normalize_pattern(pattern)


def test_consecutive_globstars_collapse():
    assert normalize_pattern("**/**") == (False, ("**",))
    assert normalize_pattern("a/**/**/b") == (False, ("a", "**", "b"))
    assert normalize_pattern("!**/**/x") == (True, ("**", "x"))


def test_nul_rejected():
    with pytest.raises(PatternError):
        normalize_pattern("a\0b")


def test_absolute_windows_path_normalization():
    assert normalize_pattern(r"C:\Users\Bob\project\src") == (
        False,
        ("C:", "Users", "Bob", "project", "src"),
    )


def test_absolute_windows_path_normalization_negation():
    assert normalize_pattern(r"!C:\Users\Bob\project\src") == (
        True,
        ("C:", "Users", "Bob", "project", "src"),
    )


def test_pattern_error_is_a_value_error():
    assert issubclass(PatternError, ValueError)


# ---- load_patterns ----


def test_load_missing_file_is_empty(tmp_path):
    assert load_patterns(tmp_path / "nope.txt") == []


def test_load_skips_blank_lines_and_comments(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text(
        "# comment\n\n  # indented comment\nsrc\n  !build  \n", encoding="utf-8"
    )
    assert load_patterns(f) == [(False, ("src",)), (True, ("build",))]


def test_load_handles_bom_and_crlf(tmp_path):
    f = tmp_path / "f.txt"
    f.write_bytes(b"\xef\xbb\xbfsrc\r\n!build\r\n")
    assert load_patterns(f) == [(False, ("src",)), (True, ("build",))]


def test_load_backslash_escapes_a_leading_hash(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("\\#notes\n", encoding="utf-8")
    assert load_patterns(f) == [(False, ("#notes",))]


def test_load_error_mentions_file_and_line(tmp_path):
    f = tmp_path / "onefile_exclude.txt"
    f.write_text("ok\n\n../oops\n", encoding="utf-8")
    with pytest.raises(PatternError) as info:
        load_patterns(f)
    message = str(info.value)
    assert "onefile_exclude.txt:3" in message
    assert "cannot contain '..'" in message


def test_load_non_utf8_is_a_clean_error(tmp_path):
    f = tmp_path / "f.txt"
    f.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(PatternError, match="not valid UTF-8"):
        load_patterns(f)
