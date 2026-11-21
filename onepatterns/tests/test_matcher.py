import itertools

from onepatterns import PatternMatcher, normalize_pattern


def make_pattern(priority, pattern):
    return (priority, *normalize_pattern(pattern))


def check(patterns, cases, permutations=True):
    orders = itertools.permutations(patterns) if permutations else [patterns]

    for order in orders:
        matcher = PatternMatcher([make_pattern(0, pattern) for pattern in order])

        for path, expected in cases.items():
            result = matcher.matches(tuple(path.split("/")))

            assert result == expected, f"""
            patterns: {order}
            path: {path}
            match: {result}
            expected: {expected}
            """.strip()


def test_include_basic():
    check(
        ["src"],
        {
            "src/main.zig": True,
            "src/core/api.zig": True,
            "other/file.zig": False,
        },
    )


def test_exclude_basic():
    check(
        ["src", "!src/private"],
        {
            "src/main.zig": True,
            "src/private/a.zig": False,
            "src/private/deep/a.zig": False,
        },
    )


def test_exclude_directory():
    check(
        ["!build"],
        {
            "src/main.zig": True,
            "build/a.o": False,
        },
    )


def test_reinclude_directory():
    check(
        ["!build", "build/cache"],
        {
            "build/a.o": False,
            "build/cache/a.o": True,
        },
    )


def test_nested_exclusions():
    check(
        ["src", "!src/generated", "!src/generated/private"],
        {
            "src/a.zig": True,
            "src/generated/a.zig": False,
            "src/generated/private/a.zig": False,
        },
    )


def test_specificity():
    check(
        ["!*.txt", "credits.txt"],
        {
            "credits.txt": True,
            "a.txt": False,
            "dir/a.txt": False,
            "image.png": False,
        },
    )

    check(
        ["*.txt", "!credits.txt"],
        {
            "credits.txt": False,
            "a.txt": True,
            "dir/a.txt": False,
            "image.png": False,
        },
    )

    check(
        ["src", "!src/private", "src/private/public"],
        {
            "src/a": True,
            "src/private/a": False,
            "src/private/public/a": True,
        },
    )

    check(
        ["!src", "src/private", "!src/private/public"],
        {
            "src/a": False,
            "src/private/a": True,
            "src/private/public/a": False,
        },
    )


def test_double_star():
    check(
        ["my_folder/**/my_file"],
        {
            "my_folder/my_file": True,
            "my_folder/a/my_file": True,
            "my_folder/a/b/c/my_file": True,
            "my_folder/a/b/c/other": False,
            "other/my_folder/a/my_file": False,
            # no file/folder information here: a path that goes below my_file
            # means my_file is a folder, and a pattern covers what is below it
            # (same rule as src/file -> src/file/a)
            "my_folder/my_file/other": True,
            "my_folder/my_file/a/other": True,
            "my_folder/other/my_file/x": True,
            "my_folder/other": False,
        },
    )


def test_double_star_zig():
    check(
        ["src/**/*.zig"],
        {
            "src/main.zig": True,
            "src/a/main.zig": True,
            "src/a/b/main.zig": True,
            "src/a/b/main.js": False,
            "src/.zig": True,
        },
    )


def test_double_star_root_zig():
    check(
        ["**/*.zig"],
        {
            ".zig": True,
            "root.zig": True,
            "src/main.zig": True,
            "src/a/main.zig": True,
            "src/a/b/main.zig": True,
            "src/a/b/main.js": False,
            "src/.zig": True,
        },
    )


def test_equal_specificity_last_one_wins():
    check(
        ["*.txt", "!*.txt"],
        {
            "a.txt": False,
        },
        permutations=False,
    )


def test_double_star_is_less_specific():
    check(
        ["**/*.zig", "!src/main.zig"],
        {
            "src/main.zig": False,
            "other/main.zig": True,
        },
    )


def test_no_patterns():
    check(
        [],
        {
            "anything": True,
            "a/b/c": True,
        },
    )


def test_root_include_and_exclude():
    check(
        ["."],
        {
            "file.txt": True,
            "dir/file.txt": True,
        },
    )

    check(
        ["!."],
        {
            "file.txt": False,
            "dir/file.txt": False,
        },
    )


def test_directory_pattern_matches_contents():
    check(
        ["src/file"],
        {
            "src/file": True,
            "src/file/a": True,
            "src": False,
            "src_other/file": False,
        },
    )


def test_special_component_names():
    check(
        ["*.txt"],
        {
            ".txt": True,
            "file.txt": True,
            "file.txt.bak": False,
            "txt": False,
        },
    )


def test_wildcard_component():
    check(
        ["a_*_b_*_c.txt"],
        {
            "a_x_b_y_c.txt": True,
            "a_test_b_world_c.txt": True,
            "a_hello_world_b_123_c.txt": True,
            "a__b__c.txt": True,
            "a_x_b_c.txt": False,
            "a_x_y.txt": False,
            "x_a_x_b_y_c.txt": False,
            "a_x_b_y_c.txt.bak": False,
            "a_b_b_c.txt": False,
            "a_b_b_b_b_c.txt": True,
        },
    )


def test_cli_overrides_file_include():
    matcher = PatternMatcher(
        [
            make_pattern(1, "!public"),  # CLI
            make_pattern(0, "public"),  # include file
        ]
    )

    assert not matcher.matches(("public", "file.txt"))


def test_specific_file_pattern_beats_generic_cli_pattern():
    matcher = PatternMatcher(
        [
            make_pattern(1, "**/*.py"),  # CLI
            make_pattern(0, "!.venv"),  # equivalent to .venv in exclude file
        ]
    )

    assert not matcher.matches((".venv", "foo.py"))


def test_single_folder_not_recursive():
    check(
        ["src"],
        {
            "src/foo.txt": True,
            "src/common/base.py": True,
        },
    )

    check(
        ["src/*"],
        {
            "src/foo.txt": True,
            "src/common/base.py": False,
        },
    )


def test_root_star_not_recursive():
    check(
        ["*"],
        {
            "src/foo.txt": False,
            "base.py": True,
        },
    )
    check(
        ["!*"],
        {
            "src/foo.txt": True,
            "base.py": False,
        },
    )


# ---- tests below are new ----


def test_only_a_bare_star_stops_the_recursion():
    # *.egg-info, build*, ... name things that may be folders: they cover
    # what is below. A lone "*" is "this level".
    check(
        ["*.egg-info"],
        {
            "a.egg-info": True,
            "a.egg-info/PKG-INFO": True,
            "b/a.egg-info": False,
        },
    )
    check(
        ["build*"],
        {
            "build_old/x/y": True,
            "build": True,
            "src/build_old": False,
        },
    )
    check(
        ["src/*/c"],
        {
            "src/a/c": True,
            "src/a/c/deep": True,
            "src/a/b/c": False,
            "src/c": False,
        },
    )


def test_star_exclusion_of_root_files_keeps_subfolders():
    check(
        ["src/**", "!*"],
        {
            "top.txt": False,
            "src/a.txt": True,
            "src/deep/b.txt": True,
        },
    )


def test_star_matches_dotfiles_and_empty():
    check(
        ["*"],
        {
            ".env": True,
            "a": True,
        },
    )
    check(
        ["pre*suf"],
        {
            "presuf": True,
            "pre_x_suf": True,
            "pre": False,
            "suf": False,
            "presu": False,
        },
    )


def test_component_matching_is_case_sensitive():
    check(["README.md"], {"README.md": True, "readme.md": False})


def test_specificity_order():
    from onepatterns import specificity

    ascending = [
        "**",
        "src/**",
        "src/a/**",
        "**/*.py",
        "**/x.py",
        "*",
        "src",
        "src/**/x.py",
        "src/*",
        "src/a",
    ]
    keys = [specificity(normalize_pattern(p)[1]) for p in ascending]
    assert keys == sorted(set(keys)), "must be strictly increasing"


def test_priority_only_breaks_exact_specificity_ties():
    # CLI "**/*.py" is less specific than the file's "!vendor": file wins
    matcher = PatternMatcher([make_pattern(1, "**/*.py"), make_pattern(0, "!vendor")])
    assert not matcher.matches(("vendor", "a.py"))
    assert matcher.matches(("src", "a.py"))
    # same pattern: CLI wins whatever the order
    for rules in (
        [make_pattern(1, "a"), make_pattern(0, "!a")],
        [make_pattern(0, "!a"), make_pattern(1, "a")],
    ):
        assert PatternMatcher(rules).matches(("a", "x"))


def test_default_follows_positive_patterns():
    assert PatternMatcher([]).default is True
    assert PatternMatcher([make_pattern(0, "!a")]).default is True
    assert PatternMatcher([make_pattern(0, "a")]).default is False
    assert (
        PatternMatcher([make_pattern(0, "!a"), make_pattern(0, "b")]).default is False
    )
    assert PatternMatcher([make_pattern(0, "a")], default=True).matches(("z",))


def test_rules_may_be_plain_tuples():
    matcher = PatternMatcher([(0, False, ("src",)), (0, True, ("src", "x"))])
    assert matcher.matches(("src", "a"))
    assert not matcher.matches(("src", "x", "a"))


def test_match_component():
    from onepatterns import match_component

    assert match_component("a", "a")
    assert not match_component("a", "ab")
    assert match_component("*", "anything")
    assert match_component("a*", "a")
    assert match_component("*a", "a")
    assert not match_component("a*a", "a")  # prefix and suffix may not overlap
    assert match_component("a*a", "aa")
    assert match_component("*.py", ".py")
    assert match_component("a**b", "ab")
    assert match_component("*x*y*", "1x2y3")
    assert not match_component("*x*y*", "1y2x3")
    assert match_component("a?b", "a?b")  # no other wildcards
    assert not match_component("a?b", "axb")
    assert match_component("[ab]", "[ab]")


def test_a_plain_inclusion_beats_a_generic_exclusion():
    # "src" has the same number of named components as "**/*.txt" but no "**",
    # so it is more specific: the txt files in src stay. To drop them, write
    # the exclusion under src, which names more components than "src" does.
    check(
        ["src", "!**/*.txt"],
        {
            "src/a.py": True,
            "src/b.txt": True,
            "docs/c.txt": False,
        },
    )
    check(
        ["src", "!src/**/*.txt"],
        {
            "src/a.py": True,
            "src/b.txt": False,
            "src/deep/c.txt": False,
        },
    )
