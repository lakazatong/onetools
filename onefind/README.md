# onefind

Find files and directories by name. Patterns are resolved from the search root; unrelated parts of the tree are not scanned.

```sh
onefind hermes
onefind a/b
onefind 'src/*.py'
onefind 'src/**/test_*.py'
onefind -d ~/projects '**/pyproject.toml'
```

`*` matches within one path component. `**` matches zero or more directory components. Patterns are case-sensitive and relative to the search root. Multiple patterns are combined; a leading `!` excludes matches from the results.

Symlinks are not followed.
