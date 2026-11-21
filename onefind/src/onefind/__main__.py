"""Find files and directories by name."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterator
from pathlib import Path

from onepatterns import PatternError, match_component, normalize_pattern


def _entries(directory: Path) -> Iterator[Path]:
    try:
        yield from directory.iterdir()
    except OSError as error:
        print(f"onefind: warning: cannot read {directory}: {error}", file=sys.stderr)


def _entry_is_dir(path: Path) -> bool | None:
    try:
        if path.is_symlink():
            return None
        if path.is_dir():
            return True
        if path.is_file():
            return False
    except OSError as error:
        print(f"onefind: warning: cannot inspect {path}: {error}", file=sys.stderr)
    return None


def _resolve(
    directory: Path,
    parts: tuple[str, ...],
    index: int,
) -> Iterator[Path]:
    component = parts[index]
    last = index == len(parts) - 1

    if component == "**":
        if last:
            for entry in _entries(directory):
                is_dir = _entry_is_dir(entry)
                if is_dir is None:
                    continue
                yield entry
                if is_dir:
                    yield from _resolve(entry, parts, index)
            return

        yield from _resolve(directory, parts, index + 1)
        for entry in _entries(directory):
            if _entry_is_dir(entry) is True:
                yield from _resolve(entry, parts, index)
        return

    if "*" not in component:
        candidates = (directory / component,)
    else:
        candidates = (
            entry
            for entry in _entries(directory)
            if match_component(component, entry.name)
        )

    for entry in candidates:
        is_dir = _entry_is_dir(entry)
        if is_dir is None:
            continue
        if last:
            yield entry
        elif is_dir:
            yield from _resolve(entry, parts, index + 1)


def iter_matches(root: Path, patterns: list[str]) -> Iterator[Path]:
    """Resolve each pattern from ``root`` without walking unrelated paths."""
    included: set[Path] = set()
    excluded: set[Path] = set()

    for pattern in patterns:
        negated, parts = normalize_pattern(pattern)
        matches = _resolve(root, parts, 0)
        (excluded if negated else included).update(matches)

    yield from sorted(included - excluded, key=lambda path: path.relative_to(root).as_posix())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="onefind",
        description="Find files and directories by name.",
        epilog=(
            "Patterns are relative to the search root. '*' matches within one "
            "path component; '**' matches any number of directory components. "
            "Names are case sensitive."
        ),
    )
    parser.add_argument("patterns", nargs="+", help="path patterns")
    parser.add_argument(
        "-d",
        "--directory",
        default=".",
        help="search root (default: current directory)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.directory).resolve()

    if not root.is_dir():
        parser.error(f"not a directory: {args.directory}")

    try:
        for path in iter_matches(root, args.patterns):
            print(path.relative_to(root).as_posix())
    except PatternError as error:
        parser.error(str(error))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
