"""onefile: bundle project files into a single text file."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from onepatterns import PatternError, Rule, normalize_pattern

from .walker import CLI_PRIORITY, is_text_file, iter_project_files  # noqa: F401

DESCRIPTION = """\
Bundle project files into one text file.

Patterns can be given on the command line. A directory may also contain
'onefile_include.txt' / 'onefile_exclude.txt' (one pattern per line, '#'
starts a comment); they apply to that directory and below, and patterns
are relative to it. Lines in onefile_exclude.txt are negated.

Patterns:
  - '*' matches any run of characters inside one path component, '**'
    matches any number of components. Case sensitive.
  - A pattern matches itself and everything below it ('src' = 'src/**'),
    except when its last component is exactly '*' ('src/*' = direct children).
  - A leading '!' excludes instead of includes. '.' means everything.
  - If there is at least one including pattern, only what it matches is
    bundled; otherwise everything is. Excluding patterns then trim that.
  - On conflicts the most specific pattern wins, then the command line over
    the files, then the later pattern.

Examples:
  onefile src/core README.md       # two specific paths
  onefile . '!node_modules'        # everything but node_modules
  onefile --dry                    # list files without writing
"""


def fence_for(content: str) -> str:
    """A backtick fence longer than any backtick run in ``content``."""
    longest = max((len(run) for run in re.findall(r"`+", content)), default=0)
    return "`" * max(3, longest + 1)


def format_entry(relative: str, content: str) -> str:
    fence = fence_for(content)
    body = content if not content or content.endswith("\n") else content + "\n"
    return f"{relative}:\n\n{fence}\n{body}{fence}\n\n"


def write_bundle(root: Path, files, output_file: Path, header: str | None = None):
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8", newline="\n") as out:
        if header:
            out.write(header)
        for path in files:
            try:
                content = path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError) as error:
                print(f"onefile: warning: skipped {path}: {error}", file=sys.stderr)
                continue
            out.write(format_entry(path.relative_to(root).as_posix(), content))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="onefile",
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("patterns", nargs="*", help="include/exclude path patterns")
    parser.add_argument(
        "-d", "--directory", default=".", help="root directory (default: .)"
    )
    parser.add_argument(
        "-o",
        "--output",
        default="onefile_out.txt",
        help="output file (default: onefile_out.txt)",
    )
    parser.add_argument(
        "--dry", action="store_true", help="only list the files that would be bundled"
    )
    parser.add_argument(
        "--header",
        action="store_true",
        help="start the output with the command and root directory",
    )
    parser.add_argument(
        "--ignore-files",
        action="store_true",
        help="ignore onefile_include.txt and onefile_exclude.txt files",
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    root = Path(args.directory).resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {args.directory}")

    try:
        base_rules = [
            Rule(CLI_PRIORITY, *normalize_pattern(pattern)) for pattern in args.patterns
        ]
    except PatternError as error:
        parser.error(str(error))

    output_file = Path(args.output).resolve()

    def warn(path: Path, error: OSError) -> None:
        print(f"onefile: warning: cannot read {path}: {error}", file=sys.stderr)

    # Collect first: a bad filter file must not leave a half written output.
    try:
        files = list(
            iter_project_files(
                root,
                base_rules,
                exclude_paths=[output_file],
                use_filter_files=not args.ignore_files,
                on_error=warn,
            )
        )
    except PatternError as error:
        print(f"onefile: error: {error}", file=sys.stderr)
        return 2

    if args.dry:
        for path in files:
            print(path.relative_to(root).as_posix())
        return 0

    header = None
    if args.header:
        command = " ".join(["onefile", *(sys.argv[1:] if argv is None else argv)])
        header = f"Generated using: {command}\nUnder {root}\n\n"

    try:
        write_bundle(root, files, output_file, header)
    except OSError as error:
        print(f"onefile: error: cannot write {output_file}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
