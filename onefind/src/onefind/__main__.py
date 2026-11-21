"""Find files and directories by name."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from onepatterns import match_component


def iter_matches(root: Path, patterns: list[str]):
    def walk(directory: Path):
        try:
            entries = sorted(directory.iterdir(), key=lambda entry: entry.name)
        except OSError as error:
            print(
                f"onefind: warning: cannot read {directory}: {error}", file=sys.stderr
            )
            return

        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                is_dir = entry.is_dir()
                is_file = entry.is_file()
            except OSError as error:
                print(
                    f"onefind: warning: cannot inspect {entry}: {error}",
                    file=sys.stderr,
                )
                continue

            if not (is_dir or is_file):
                continue

            if any(match_component(pattern, entry.name) for pattern in patterns):
                yield entry

            if is_dir:
                yield from walk(entry)

    yield from walk(root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="onefind",
        description="Recursively search file and directory names.",
        epilog=(
            "A query without '*' is a case-sensitive substring. "
            "Use '*' as a wildcard. Searches names only, never file contents."
        ),
    )
    parser.add_argument(
        "patterns", nargs="+", help="patterns for the onepatterns package"
    )
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

    for path in iter_matches(root, args.patterns):
        print(path.relative_to(root).as_posix())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
