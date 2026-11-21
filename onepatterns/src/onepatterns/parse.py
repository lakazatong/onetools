"""Turning user-supplied pattern strings into ``(negated, parts)``."""

from __future__ import annotations

from pathlib import Path

GLOBSTAR = "**"


class PatternError(ValueError):
    """An invalid pattern. The message is meant to be shown to the user as is."""


def normalize_pattern(value: str) -> tuple[bool, tuple[str, ...]]:
    """Parse one pattern into ``(negated, components)``.

    - ``\\`` is treated as ``/`` so Windows paths work.
    - A leading ``!`` negates. ``!`` anywhere else is an error.
    - Empty and ``.`` components are dropped (``./src//x/.`` -> ``src/x``),
      leading ``/`` included. ``...`` and friends are ordinary names.
    - ``..`` is rejected, a pattern can never leave the root.
    - A pattern with no component left (``.``, ``/``, ``./``) means everything,
      i.e. ``**``. Consecutive ``**`` collapse into one.
    """
    original = value

    if "\0" in value:
        raise PatternError(f"Invalid pattern {original!r}: contains a NUL character")

    value = value.replace("\\", "/")

    negated = value.startswith("!")
    if negated:
        value = value[1:]
    if "!" in value:
        raise PatternError(
            f"Invalid pattern {original!r}: '!' is only allowed as the first character"
        )

    parts: list[str] = []
    for part in value.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise PatternError(
                f"Pattern cannot contain '..' (would escape root): {original!r}"
            )
        if part == GLOBSTAR and parts and parts[-1] == GLOBSTAR:
            continue
        parts.append(part)

    return negated, tuple(parts) or (GLOBSTAR,)


def load_patterns(filter_file) -> list[tuple[bool, tuple[str, ...]]]:
    """Read patterns from a file, one per line.

    Blank lines and lines starting with ``#`` are ignored (after stripping).
    A missing file is an empty list. A UTF-8 BOM is tolerated. Errors are
    reported as ``PatternError("<file>:<line>: ...")``.
    """
    path = Path(filter_file)
    if not path.is_file():
        return []

    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PatternError(f"{path}: not valid UTF-8 ({exc.reason})") from None
    except OSError as exc:
        raise PatternError(f"{path}: {exc.strerror or exc}") from None

    patterns = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            patterns.append(normalize_pattern(line))
        except PatternError as exc:
            raise PatternError(f"{path}:{lineno}: {exc}") from None
    return patterns
