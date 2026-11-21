from onefile.__main__ import iter_project_files

from onepatterns import normalize_pattern


def make_pattern(priority, pattern):
    return (priority, *normalize_pattern(pattern))


def make_tree(root, paths):
    for path in paths:
        path = root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")


def check(tmp_path, patterns, cases, filter_files=None):
    make_tree(tmp_path, cases)

    for name, content in (filter_files or {}).items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    matcher = [make_pattern(1, pattern) for pattern in patterns]

    always_exclude = {"onefile_include.txt", "onefile_exclude.txt"}

    result = {
        path.relative_to(tmp_path).as_posix()
        for path in iter_project_files(
            tmp_path,
            matcher,
            always_exclude,
        )
    }

    expected = {path for path, included in cases.items() if included}

    assert result == expected


def test_cli_generic_include_does_not_override_specific_file_exclude(tmp_path):
    check(
        tmp_path,
        ["**/*.py", "!.venv"],
        {
            ".venv/foo.py": False,
            "foo.py": True,
        },
    )


def test_cli_specific_include_overrides_file_exclude(tmp_path):
    check(
        tmp_path,
        [".venv/foo.py"],
        {
            ".venv/foo.py": True,
        },
        filter_files={"onefile_exclude.txt": ".venv\n"},
    )


def test_specific_file_exclude_overrides_generic_include(tmp_path):
    check(
        tmp_path,
        ["src/**"],
        {
            "src/__init__.py": False,
        },
        filter_files={"onefile_exclude.txt": "**/__init__.py\n"},
    )


def test_egg_info_excluded_from_src_glob(tmp_path):
    check(
        tmp_path,
        ["src/**"],
        {
            "src/mypackage/dead/beef.py": True,
            "src/mypackage/foo.py": True,
            "src/mypackage.egg-info/PKG-INFO": False,
        },
        filter_files={"onefile_exclude.txt": "**/*.egg-info\n"},
    )


def test_cli_wins_same_specificity(tmp_path):
    check(
        tmp_path,
        ["src/foo.py"],
        {
            "src/foo.py": True,
        },
        filter_files={"onefile_exclude.txt": "src/foo.py\n"},
    )


def test_single_folder_not_recursive(tmp_path):
    check(
        tmp_path,
        ["src"],
        {
            "src/foo.py": True,
            "src/common/base.py": True,
            "other/hello.txt": False,
        },
    )

    check(
        tmp_path,
        ["src/*"],
        {
            "src/foo.py": True,
            "src/common/base.py": False,
            "other/hello.txt": False,
        },
    )


def test_root_star_not_recursive(tmp_path):
    check(
        tmp_path,
        ["*"],
        {
            "src/foo.txt": False,
            "base.py": True,
        },
    )

    check(
        tmp_path,
        ["!*"],
        {
            "src/foo.txt": True,
            "base.py": False,
        },
    )


def test_real_case(tmp_path):
    check(
        tmp_path,
        [],
        {
            "src/main.jsx": True,
        },
        filter_files={
            "onefile_exclude.txt": """.build
.vscode
desktop/external
mobile/android/.gradle
mobile/android/.kotlin
mobile/android/app/build
mobile/android/app/src/main/res
mobile/android/gradle
mobile/android/gradlew
mobile/android/gradlew.bat
node_modules
src/assets
!.
*
!index.html
!vite.config.js"""
        },
    )
