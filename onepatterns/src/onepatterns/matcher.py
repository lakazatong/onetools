"""Component-wise pattern matching with specificity based precedence.

Semantics
---------
A pattern is a tuple of components. Paths are tuples of names.

* ``*`` inside a component matches any run of characters (possibly empty).
  It is the only wildcard. Matching is case sensitive.
* A component that is exactly ``**`` matches zero or more whole components.
* A pattern covers the path it names *and everything below it*: ``src/file``
  behaves like ``src/file/**``. The single exception is a last component that
  is exactly ``*``: ``src/*`` and ``*`` stay at that depth.
  (``*.txt``, ``build*`` and so on do cover what is below a match.)

Precedence, when several patterns match a path:

1. the most *specific* pattern wins (see :func:`specificity`),
2. then the higher ``priority`` (the CLI beats the include/exclude files),
3. then the later one.

If nothing matches, the path is included only when there is no positive
(non-negated) pattern at all. In other words, positive patterns form a
whitelist and negative ones trim it; with no whitelist everything is the
starting point.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import NamedTuple

from .parse import GLOBSTAR


class Rule(NamedTuple):
    """A pattern plus where it came from. Plain 3-tuples are accepted too."""

    priority: int
    negated: bool
    parts: tuple[str, ...]


def match_component(pattern: str, name: str) -> bool:
    """Match one path component against one pattern component (``*`` only)."""
    if "*" not in pattern:
        return pattern == name

    first, *middle, last = pattern.split("*")
    if len(name) < len(first) + len(last):
        return False
    if not name.startswith(first) or not name.endswith(last):
        return False

    position, end = len(first), len(name) - len(last)
    for piece in middle:
        found = name.find(piece, position, end)
        if found == -1:
            return False
        position = found + len(piece)
    return True


def effective_parts(parts: tuple[str, ...]) -> tuple[str, ...]:
    """Make "covers everything below" explicit by appending ``**``."""
    if parts[-1] in ("*", GLOBSTAR):
        return parts
    return parts + (GLOBSTAR,)


def specificity(parts: tuple[str, ...]) -> tuple[bool, int, int, int]:
    """Rank a pattern, bigger is more specific. Compared in this order:

    1. does not end with ``**`` (the right-most component names something)
    2. more non-``**`` components (``src/a`` > ``src``)
    3. fewer ``**`` (``src`` > ``**/src``)
    4. fewer wildcard components (``credits.txt`` > ``*.txt``)
    """
    literal = [part for part in parts if part != GLOBSTAR]
    globstars = len(parts) - len(literal)
    wildcards = sum("*" in part for part in literal)
    return (parts[-1] != GLOBSTAR, len(literal), -globstars, -wildcards)


def _states_after(pattern: tuple[str, ...], path: Sequence[str]) -> set[int]:
    """Positions in ``pattern`` that can be reached after consuming ``path``.

    Position ``len(pattern)`` means the whole pattern has been matched.
    """
    size = len(pattern)

    def close(states: set[int]) -> set[int]:
        # a ``**`` may also match nothing
        for state in sorted(states):
            while state < size and pattern[state] == GLOBSTAR:
                state += 1
                states.add(state)
        return states

    states = close({0})
    for name in path:
        following: set[int] = set()
        for state in states:
            if state >= size:
                continue
            if pattern[state] == GLOBSTAR:
                following.add(state)
            elif match_component(pattern[state], name):
                following.add(state + 1)
        states = close(following)
        if not states:
            break
    return states


class _Entry:
    __slots__ = ("key", "pattern", "rule", "size", "tail")

    def __init__(self, rule: Rule, index: int):
        self.rule = rule
        self.pattern = effective_parts(rule.parts)
        self.key = (specificity(rule.parts), rule.priority, index)
        self.size = len(self.pattern)
        # from this position on, only ``**`` is left (``size`` if there is none)
        tail = self.size
        while tail > 0 and self.pattern[tail - 1] == GLOBSTAR:
            tail -= 1
        self.tail = tail


class PatternMatcher:
    """Decides whether paths are included by a list of rules.

    ``rules`` are ``(priority, negated, parts)``; their order matters (later
    wins ties). ``default`` is what a path matched by nothing gets; ``None``
    means "include only if there is no positive rule".
    """

    def __init__(self, rules: Iterable[Sequence], default: bool | None = None):
        self.rules = [Rule(*rule) for rule in rules]
        if default is None:
            default = not any(not rule.negated for rule in self.rules)
        self.default = default
        # most specific first, so the first hit is the winner
        self._entries = sorted(
            (_Entry(rule, index) for index, rule in enumerate(self.rules)),
            key=lambda entry: entry.key,
            reverse=True,
        )

    def matches(self, path_parts: Sequence[str]) -> bool:
        """Is this path (a file, normally) included?"""
        path = tuple(path_parts)
        for entry in self._entries:
            if entry.size in _states_after(entry.pattern, path):
                return not entry.rule.negated
        return self.default

    def can_have_matches_below(self, path_parts: Sequence[str]) -> bool:
        """May some path strictly below this directory be included?

        Used to skip directories. It may say True when nothing ends up
        included, but never False when something would be: skipping a
        directory must not change the result.
        """
        path = tuple(path_parts)
        positive_can_match = False

        for entry in self._entries:  # most specific first
            states = _states_after(entry.pattern, path)
            if not any(state < entry.size for state in states):
                continue  # this rule can't match anything below
            if not entry.rule.negated:
                positive_can_match = True
            elif any(entry.tail <= state < entry.size for state in states):
                # Everything below is matched by this negative rule. The only
                # way out is a more specific positive rule, seen just before.
                return positive_can_match

        return self.default or positive_can_match
