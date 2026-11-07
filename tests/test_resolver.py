"""Resolver tests (SPEC.md sections 6 and 7, section 10 resolver list).

THESE TESTS FAIL until the owner writes resolve() in
src/repolens/python/resolver.py. That is expected (decision D11). Do not skip
or weaken them.
"""

from __future__ import annotations

from helpers import FIXTURES
from repolens.model import EdgeKind, ImportClass, Module
from repolens.output import to_json
from repolens.python.analyzer import analyze
from repolens.python.resolver import resolve
from repolens.python.roots import module_id

LOCAL = ImportClass.LOCAL
STDLIB = ImportClass.STDLIB
EXTERNAL = ImportClass.EXTERNAL
UNRESOLVED = ImportClass.UNRESOLVED


def importer(path: str, roots: list[str] | None = None) -> Module:
    roots = roots or ["."]
    return Module(module_id(path, roots), "python", path)


def known(*paths: str, roots: list[str] | None = None) -> set[str]:
    """Module ids for a pretend repository holding these files."""
    roots = roots or ["."]
    return {module_id(path, roots) for path in paths}


# --- absolute imports -------------------------------------------------------


def test_import_package_module_file_is_local() -> None:
    repo = known("main.py", "app/__init__.py", "app/auth.py")
    assert resolve(importer("main.py"), "app.auth", [], 0, repo) == [("app.auth", LOCAL)]


def test_import_package_init_file_is_local() -> None:
    repo = known("main.py", "app/__init__.py", "app/auth/__init__.py")
    assert resolve(importer("main.py"), "app.auth", [], 0, repo) == [("app.auth", LOCAL)]


def test_import_os_is_stdlib() -> None:
    assert resolve(importer("main.py"), "os", [], 0, known("main.py")) == [("os", STDLIB)]


def test_import_requests_is_external() -> None:
    assert resolve(importer("main.py"), "requests", [], 0, known("main.py")) == [
        ("requests", EXTERNAL)
    ]


def test_import_missing_module_of_local_package_is_unresolved() -> None:
    repo = known("main.py", "app/__init__.py", "app/auth.py")
    assert resolve(importer("main.py"), "app.missing", [], 0, repo) == [
        ("app.missing", UNRESOLVED)
    ]


# --- from-imports -------------------------------------------------------------


def test_from_package_import_existing_module() -> None:
    repo = known("main.py", "app/__init__.py", "app/auth.py")
    assert resolve(importer("main.py"), "app", ["auth"], 0, repo) == [("app.auth", LOCAL)]


def test_from_package_import_name_that_is_not_a_module() -> None:
    repo = known("main.py", "app/__init__.py", "app/other.py")
    assert resolve(importer("main.py"), "app", ["auth"], 0, repo) == [("app", LOCAL)]


def test_from_non_local_module_uses_module_part_only() -> None:
    assert resolve(importer("main.py"), "os", ["path"], 0, known("main.py")) == [("os", STDLIB)]


# --- relative imports ---------------------------------------------------------


def test_from_dot_import_resolves_against_importer_package() -> None:
    repo = known("app/__init__.py", "app/service.py", "app/x.py")
    assert resolve(importer("app/service.py"), None, ["x"], 1, repo) == [("app.x", LOCAL)]


def test_from_dot_dot_core_import_resolves_two_levels_up() -> None:
    repo = known(
        "app/__init__.py",
        "app/auth/__init__.py",
        "app/auth/service.py",
        "app/core/__init__.py",
        "app/core/y.py",
    )
    assert resolve(importer("app/auth/service.py"), "core", ["y"], 2, repo) == [
        ("app.core.y", LOCAL)
    ]


def test_from_dot_import_inside_init_uses_that_package() -> None:
    repo = known("app/__init__.py", "app/auth/__init__.py", "app/auth/x.py")
    assert resolve(importer("app/auth/__init__.py"), None, ["x"], 1, repo) == [
        ("app.auth.x", LOCAL)
    ]


def test_relative_import_above_root_is_unresolved() -> None:
    repo = known("app/__init__.py", "app/service.py", "x.py")
    result = resolve(importer("app/service.py"), None, ["x"], 3, repo)
    assert result
    assert all(classification is UNRESOLVED for _, classification in result)


# --- layouts and packages -----------------------------------------------------


def test_src_layout_import_resolves_under_src() -> None:
    roots = ["src", "."]
    repo = known("src/mypkg/__init__.py", "src/mypkg/x.py", "tests/test_x.py", roots=roots)
    assert resolve(importer("tests/test_x.py", roots), "mypkg.x", [], 0, repo) == [
        ("mypkg.x", LOCAL)
    ]


def test_namespace_package_counts_as_package() -> None:
    repo = known("main.py", "ns/mod.py")  # ns has no __init__.py
    assert resolve(importer("main.py"), "ns.mod", [], 0, repo) == [("ns.mod", LOCAL)]
    assert resolve(importer("main.py"), "ns", ["mod"], 0, repo) == [("ns.mod", LOCAL)]


def test_local_logging_module_wins_over_stdlib() -> None:
    repo = known("main.py", "logging.py")
    assert resolve(importer("main.py"), "logging", [], 0, repo) == [("logging", LOCAL)]


def test_local_logging_package_without_handlers_is_unresolved() -> None:
    repo = known("main.py", "logging/__init__.py")
    assert resolve(importer("main.py"), "logging.handlers", [], 0, repo) == [
        ("logging.handlers", UNRESOLVED)
    ]


# --- end to end: these also need resolve() ------------------------------------


def test_flat_project_matches_spec_example() -> None:
    expected = (FIXTURES / "expected" / "flat_project.json").read_text(encoding="utf-8")
    assert to_json(analyze(FIXTURES / "flat_project")) == expected


def test_src_project_edges_are_local() -> None:
    result = analyze(FIXTURES / "src_project")
    edges = {(e.source, e.target, e.classification) for e in result.edges}
    assert edges == {
        ("mypkg.y", "mypkg.x", LOCAL),
        ("tests.test_x", "mypkg.x", LOCAL),
    }


def test_src_package_import_resolves_to_src_app() -> None:
    # src/__init__.py exists, so src is a normal package and roots = ["."]
    # (D35). `x` is a name inside src/app/__init__.py, not a module.
    result = analyze(FIXTURES / "src_package_project")
    edges = {(e.source, e.target, e.classification) for e in result.edges}
    assert edges == {("main", "src.app", LOCAL)}


def test_literal_dynamic_import_is_classified_and_stays_dynamic() -> None:
    result = analyze(FIXTURES / "imports_project")
    dynamic = {
        (e.target, e.classification) for e in result.edges if e.kind is EdgeKind.DYNAMIC
    }
    # app is local, app.plugins does not exist -> unresolved (D7, D14).
    assert dynamic == {
        ("app.plugins.alpha", UNRESOLVED),
        ("app.plugins.gamma", UNRESOLVED),
    }


def test_scanning_twice_is_byte_identical() -> None:
    first = to_json(analyze(FIXTURES / "imports_project"))
    second = to_json(analyze(FIXTURES / "imports_project"))
    assert first.encode("utf-8") == second.encode("utf-8")
