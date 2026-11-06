"""Analyzer: a full scan with a stand-in resolver.

Checks that the steps are connected correctly: a broken file does not stop
the scan, duplicate edges are removed, and module ids follow the roots.
"""

from __future__ import annotations

from pathlib import Path

from helpers import FIXTURES, fake_resolve
from repolens.model import EdgeKind, FileError
from repolens.python.analyzer import analyze


def test_syntax_error_file_is_reported_and_scan_continues() -> None:
    result = analyze(FIXTURES / "imports_project", resolve_fn=fake_resolve)

    assert result.errors == [FileError("app/broken.py", 2, "SyntaxError")]
    # The broken file is still listed as a module ...
    assert "app.broken" in {m.id for m in result.modules}
    # ... and the files after it were still analysed.
    assert any(e.source == "app.auth.service" for e in result.edges)


def test_dynamic_edges_keep_their_kind() -> None:
    result = analyze(FIXTURES / "imports_project", resolve_fn=fake_resolve)
    dynamic = sorted(e.target for e in result.edges if e.kind is EdgeKind.DYNAMIC)
    assert dynamic == ["app.plugins.alpha", "app.plugins.gamma"]
    assert len(result.observations) == 2


def test_identical_edges_are_removed(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("import os, os\n", encoding="utf-8")
    result = analyze(tmp_path, resolve_fn=fake_resolve)
    assert len(result.edges) == 1


def test_same_import_on_two_lines_gives_two_edges(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("import os\nimport os\n", encoding="utf-8")
    result = analyze(tmp_path, resolve_fn=fake_resolve)
    assert sorted(e.evidence.line for e in result.edges) == [1, 2]


def test_earlier_root_wins_and_shadowed_file_is_an_error() -> None:
    # src/app/x.py and app/x.py both get the id "app.x". Roots are
    # ["src", "."], so the file under "src" wins (D33).
    result = analyze(FIXTURES / "shadow_project", resolve_fn=fake_resolve)

    assert result.language_roots == {"python": ["src", "."]}
    assert [(m.id, m.path) for m in result.modules] == [("app.x", "src/app/x.py")]
    assert result.errors == [FileError("app/x.py", None, "ShadowedModule")]
    # The shadowed file is not analysed, so its `import json` gives no edge.
    assert {e.evidence.file for e in result.edges} == {"src/app/x.py"}


def test_package_init_wins_over_module_file_in_same_root(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "auth").mkdir()
    (tmp_path / "app" / "auth.py").write_text("", encoding="utf-8")
    (tmp_path / "app" / "auth" / "__init__.py").write_text("", encoding="utf-8")

    result = analyze(tmp_path, resolve_fn=fake_resolve)

    assert [(m.id, m.path) for m in result.modules] == [("app.auth", "app/auth/__init__.py")]
    assert result.errors == [FileError("app/auth.py", None, "ShadowedModule")]


def test_src_project_ids_and_roots() -> None:
    result = analyze(FIXTURES / "src_project", resolve_fn=fake_resolve)
    assert result.language_roots == {"python": ["src", "."]}
    assert sorted(m.id for m in result.modules) == ["mypkg", "mypkg.x", "mypkg.y", "tests.test_x"]
