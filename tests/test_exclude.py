"""--exclude PATTERN (SPEC.md section 4, decision D50).

The fixture tests/fixtures/exclude_project has:
    app/__init__.py, app/core.py          the real code
    tests/test_core.py                    a test file
    tests/fixtures/sample/app.py          a nested sample project
"""

from __future__ import annotations

import json
from pathlib import Path

from helpers import FIXTURES
from repolens import cli
from repolens.scanner import remove_excluded

PROJECT = FIXTURES / "exclude_project"


def scan(tmp_path: Path, *exclude: str) -> bytes:
    """Run the CLI with the given --exclude patterns and return the JSON bytes."""
    target = tmp_path / "graph.json"
    args = ["scan", str(PROJECT), "-o", str(target)]
    for pattern in exclude:
        args += ["--exclude", pattern]
    assert cli.main(args) == 0
    return target.read_bytes()


def module_paths(data: bytes) -> list[str]:
    return [module["path"] for module in json.loads(data)["modules"]]


def test_no_pattern_scans_everything(tmp_path: Path) -> None:
    assert module_paths(scan(tmp_path)) == [
        "app/__init__.py",
        "app/core.py",
        "tests/fixtures/sample/app.py",
        "tests/test_core.py",
    ]


def test_one_pattern(tmp_path: Path) -> None:
    data = scan(tmp_path, "tests/fixtures/*")
    assert module_paths(data) == ["app/__init__.py", "app/core.py", "tests/test_core.py"]
    # Excluded files are not modules, so nothing from them appears anywhere.
    assert "tests/fixtures" not in data.decode("utf-8")


def test_two_patterns(tmp_path: Path) -> None:
    data = scan(tmp_path, "tests/fixtures/*", "tests/test_*.py")
    assert module_paths(data) == ["app/__init__.py", "app/core.py"]


def test_pattern_that_matches_nothing_changes_nothing(tmp_path: Path) -> None:
    assert scan(tmp_path, "docs/*") == scan(tmp_path)


def test_same_inputs_give_byte_identical_output(tmp_path: Path) -> None:
    first = scan(tmp_path, "tests/fixtures/*", "tests/test_*.py")
    second = scan(tmp_path, "tests/fixtures/*", "tests/test_*.py")
    assert first == second
    # The order of the patterns does not matter either.
    assert scan(tmp_path, "tests/test_*.py", "tests/fixtures/*") == first


def test_star_also_matches_slash() -> None:
    paths = ["a.py", "pkg/a.py", "pkg/deep/er/a.py"]
    assert remove_excluded(paths, ["pkg/*"]) == ["a.py"]
    assert remove_excluded(paths, ["*/a.py"]) == ["a.py"]


def test_matching_is_case_sensitive_on_every_machine() -> None:
    assert remove_excluded(["Tests/x.py"], ["tests/*"]) == ["Tests/x.py"]
