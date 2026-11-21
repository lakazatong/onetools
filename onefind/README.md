# onefind

A small recursive filename and directory-name search utility. It never reads file contents.

```bash
onefind config
onefind "*.py"
onefind "test*" -d ~/projects
```

A query without `*` is treated as a case-sensitive substring. A query containing `*` is treated as a wildcard pattern. Multiple queries are combined with OR. Results are printed as paths relative to the search root.

Symlinks are not followed. Unreadable directories produce a warning and are skipped.

## Dependencies

`onefind` reuses `match_component` from the existing `onepatterns` package.

## Packaging integration

Add the following entry point to the existing project's `[project.scripts]` section:

```toml
onefind = "onefind.__main__:main"
```

Include `onefind` in the project's package discovery. The package source is under `src/onefind`.
