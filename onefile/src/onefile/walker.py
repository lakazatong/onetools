"""Walking a project tree and deciding which files are bundled."""

from __future__ import annotations

import codecs
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

from onepatterns import PatternMatcher, Rule, load_patterns

INCLUDE_FILE = "onefile_include.txt"
EXCLUDE_FILE = "onefile_exclude.txt"
FILTER_FILES = frozenset({INCLUDE_FILE, EXCLUDE_FILE})

CLI_PRIORITY = 1
FILE_PRIORITY = 0


def is_text_file(path, probe_size: int = 8192) -> bool:
    """Cheap check: no NUL byte and valid UTF-8 in the first ``probe_size`` bytes."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(probe_size)
    except OSError:
        return False

    if b"\x00" in chunk:
        return False

    # A multibyte character may be cut by the probe boundary: only be strict
    # when the whole file was read.
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        decoder.decode(chunk, final=len(chunk) < probe_size)
    except UnicodeDecodeError:
        return False
    return True


def iter_project_files(
    root_dir,
    base_rules: Iterable,
    always_exclude: Iterable[str] = (),
    *,
    use_filter_files: bool = True,
    exclude_paths: Iterable = (),
    on_error: Callable[[Path, OSError], None] | None = None,
) -> Iterator[Path]:
    """Yield the text files under ``root_dir`` selected by the rules.

    ``base_rules`` are ``(priority, negated, parts)`` from the command line.
    Each directory entered may add the rules of its ``onefile_include.txt``
    and ``onefile_exclude.txt`` (the latter negated, then toggled), relative
    to that directory, which apply to that directory and below. A directory
    that is skipped is never entered, so the filter files inside are not read.

    Never yielded: files named in ``always_exclude`` (plus the filter files
    themselves), files in ``exclude_paths`` (the output file) and symlinks,
    which are not followed. Unreadable directories are reported to
    ``on_error`` and skipped. A bad filter file raises ``PatternError``.
    """
    root = Path(root_dir)
    excluded_names = FILTER_FILES | frozenset(always_exclude)
    excluded_paths = frozenset(Path(path).resolve() for path in exclude_paths)
    excluded_path_names = {path.name for path in excluded_paths}
    base = tuple(Rule(*rule) for rule in base_rules)

    def report(path: Path, error: OSError) -> None:
        if on_error is not None:
            on_error(path, error)

    def walk(directory: Path, parts: tuple[str, ...], inherited: tuple[Rule, ...]):
        rules = list(inherited)
        if use_filter_files:
            for filename, toggle in ((INCLUDE_FILE, False), (EXCLUDE_FILE, True)):
                for negated, relative in load_patterns(directory / filename):
                    rules.append(
                        Rule(FILE_PRIORITY, negated != toggle, parts + relative)
                    )
        matcher = PatternMatcher(rules)

        try:
            entries = sorted(directory.iterdir(), key=lambda entry: entry.name)
        except OSError as error:
            report(directory, error)
            return

        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                is_dir = entry.is_dir()
                is_file = not is_dir and entry.is_file()
            except OSError as error:
                report(entry, error)
                continue

            entry_parts = parts + (entry.name,)

            if is_dir:
                if matcher.can_have_matches_below(entry_parts):
                    yield from walk(entry, entry_parts, tuple(rules))
            elif is_file:
                if entry.name in excluded_names:
                    continue
                if (
                    entry.name in excluded_path_names
                    and entry.resolve() in excluded_paths
                ):
                    continue
                if matcher.matches(entry_parts) and is_text_file(entry):
                    yield entry

    yield from walk(root, (), base)
