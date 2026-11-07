"""Source roots and module ids (SPEC.md sections 5 and 7, decision D9)."""

from __future__ import annotations

from helpers import FIXTURES
from repolens.python.roots import detect_roots, module_id
from repolens.scanner import scan_python_files


def test_flat_project_root_is_dot() -> None:
    files = scan_python_files(FIXTURES / "flat_project")
    assert detect_roots(files) == ["."]


def test_src_project_roots_are_src_then_dot() -> None:
    files = scan_python_files(FIXTURES / "src_project")
    assert detect_roots(files) == ["src", "."]


def test_src_with_init_is_a_package_not_a_root() -> None:
    files = scan_python_files(FIXTURES / "src_package_project")
    roots = detect_roots(files)
    assert roots == ["."]
    assert {path: module_id(path, roots) for path in files} == {
        "main.py": "main",
        "src/__init__.py": "src",
        "src/app/__init__.py": "src.app",
    }


def test_longest_root_gives_the_module_id() -> None:
    roots = ["src", "."]
    assert module_id("src/mypkg/x.py", roots) == "mypkg.x"
    assert module_id("tests/test_x.py", roots) == "tests.test_x"


def test_src_project_module_ids() -> None:
    files = scan_python_files(FIXTURES / "src_project")
    roots = detect_roots(files)
    ids = {path: module_id(path, roots) for path in files}
    assert ids == {
        "src/mypkg/__init__.py": "mypkg",
        "src/mypkg/x.py": "mypkg.x",
        "src/mypkg/y.py": "mypkg.y",
        "tests/test_x.py": "tests.test_x",
    }


def test_init_file_gets_the_package_id() -> None:
    assert module_id("app/auth/__init__.py", ["."]) == "app.auth"
    assert module_id("app/auth.py", ["."]) == "app.auth"


def test_non_identifier_folder_keeps_its_name() -> None:
    assert module_id("my-scripts/run.py", ["."]) == "my-scripts.run"


def test_root_init_file_falls_back_to_shorter_root() -> None:
    # src/__init__.py has no id under root "src", so the "." root is used.
    assert module_id("src/__init__.py", ["src", "."]) == "src"
