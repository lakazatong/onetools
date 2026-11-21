"""``can_have_matches_below`` is what lets the walker skip directories.

It must never change the result: a file is bundled iff ``matches`` says so,
skipped directories or not.
"""

import random

from onepatterns import PatternMatcher, normalize_pattern


def make_pattern(priority, pattern):
    return (priority, *normalize_pattern(pattern))


def matcher_for(*patterns, priority=0):
    return PatternMatcher([make_pattern(priority, pattern) for pattern in patterns])


def test_excluded_directory_is_skipped():
    matcher = matcher_for("!build")
    assert not matcher.can_have_matches_below(("build",))
    assert not matcher.can_have_matches_below(("build", "sub"))
    assert matcher.can_have_matches_below(("src",))


def test_directory_outside_every_include_is_skipped():
    matcher = matcher_for("src")
    assert matcher.can_have_matches_below(("src",))
    assert matcher.can_have_matches_below(("src", "a", "b"))
    assert not matcher.can_have_matches_below(("other",))


def test_reincluded_subdirectory_keeps_its_parents_open():
    matcher = matcher_for("!build", "build/cache")
    assert matcher.can_have_matches_below(("build",))
    assert matcher.can_have_matches_below(("build", "cache"))
    assert matcher.can_have_matches_below(("build", "cache", "deep"))
    assert not matcher.can_have_matches_below(("build", "other"))


def test_single_level_patterns_do_not_open_subdirectories():
    matcher = matcher_for("src/*")
    assert matcher.can_have_matches_below(("src",))
    assert not matcher.can_have_matches_below(("src", "common"))
    assert not matcher_for("*").can_have_matches_below(("src",))


def test_single_level_exclusion_keeps_subdirectories():
    matcher = matcher_for("!*")
    assert matcher.can_have_matches_below(("src",))


def test_double_star_exclusion():
    matcher = matcher_for("src/**", "!**/node_modules")
    assert matcher.can_have_matches_below(("src",))
    assert not matcher.can_have_matches_below(("src", "node_modules"))
    assert not matcher.can_have_matches_below(("src", "a", "node_modules"))
    assert matcher.can_have_matches_below(("src", "a"))


def test_specific_include_below_generic_exclusion_of_a_glob():
    matcher = matcher_for("!**/build", "src/build/keep.txt")
    assert matcher.can_have_matches_below(("src", "build"))
    assert matcher.can_have_matches_below(("src",))
    assert not matcher.can_have_matches_below(("lib", "build"))


NAMES = ["a", "b", "c", "x.py", "y.txt"]
COMPONENTS = ["a", "b", "c", "*", "**", "*.py", "x.py", "y*", "a*"]


def random_rules(rng):
    rules = []
    for _ in range(rng.randint(0, 5)):
        pattern = "/".join(rng.choice(COMPONENTS) for _ in range(rng.randint(1, 3)))
        if rng.random() < 0.5:
            pattern = "!" + pattern
        rules.append(make_pattern(rng.randint(0, 1), pattern))
    return rules


def random_files(rng):
    files = set()
    for _ in range(rng.randint(1, 14)):
        files.add(tuple(rng.choice(NAMES) for _ in range(rng.randint(1, 4))))
    # a name is either a file or a folder, never both
    return [f for f in files if not any(g != f and g[: len(f)] == f for g in files)]


def test_skipping_directories_never_changes_the_result():
    rng = random.Random(1234)
    for _ in range(1500):
        rules = random_rules(rng)
        files = random_files(rng)
        matcher = PatternMatcher(rules)

        expected = {f for f in files if matcher.matches(f)}
        walked = {
            f
            for f in files
            if all(matcher.can_have_matches_below(f[:i]) for i in range(1, len(f)))
            and matcher.matches(f)
        }

        assert walked == expected, f"""
        rules: {rules}
        files: {sorted(files)}
        walked: {sorted(walked)}
        expected: {sorted(expected)}
        """.strip()
