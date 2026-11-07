"""Output: deterministic JSON, no backslashes, no absolute paths (SPEC.md section 8).

These tests use helpers.fake_resolve, so they do not depend on the owner's
resolve(). They check the JSON format, not the resolution.
"""

from __future__ import annotations

import json
from pathlib import Path

from helpers import FIXTURES, fake_resolve
from repolens.model import Edge, EdgeKind, Evidence, FileError, ImportClass, ScanResult
from repolens.output import to_json
from repolens.python.analyzer import analyze

PROJECT = FIXTURES / "imports_project"


def _scan(path: Path) -> str:
    return to_json(analyze(path, resolve_fn=fake_resolve))


def test_same_fixture_twice_is_byte_identical() -> None:
    first = _scan(PROJECT).encode("utf-8")
    second = _scan(PROJECT).encode("utf-8")
    assert first == second


def _strings(value: object) -> list[str]:
    """Every string value in decoded JSON, at any depth."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for item in value.values() for s in _strings(item)]
    if isinstance(value, list):
        return [s for item in value for s in _strings(item)]
    return []


def test_output_has_no_backslashes() -> None:
    # Check the decoded values, not the raw text: in raw JSON a double quote
    # inside evidence text is written as \" and that backslash is only JSON
    # escaping, not part of the value.
    values = _strings(json.loads(_scan(PROJECT)))
    assert values
    for value in values:
        assert "\\" not in value


def test_output_has_no_absolute_paths() -> None:
    text = _scan(PROJECT)
    for form in [str(PROJECT.resolve()), PROJECT.resolve().as_posix(), str(Path.home())]:
        assert form not in text

    data = json.loads(text)
    paths = [m["path"] for m in data["modules"]]
    paths += [e["evidence"]["file"] for e in data["edges"]]
    paths += [o["file"] for o in data["observations"]]
    paths += [e["file"] for e in data["errors"]]
    assert paths
    for path in paths:
        assert not path.startswith("/")
        assert ":" not in path  # no Windows drive letter such as C:
        assert not Path(path).is_absolute()


def test_top_level_keys_and_trailing_newline() -> None:
    text = _scan(PROJECT)
    assert text.endswith("}\n")
    assert sorted(json.loads(text)) == [
        "cycles",
        "edges",
        "errors",
        "language_roots",
        "modules",
        "observations",
        "schema_version",
    ]
    assert json.loads(text)["schema_version"] == 2


def test_lists_are_sorted() -> None:
    def edge(source: str, target: str, line: int, kind: EdgeKind = EdgeKind.IMPORT) -> Edge:
        return Edge(source, target, kind, ImportClass.EXTERNAL, Evidence("a.py", line, "x"))

    result = ScanResult(
        language_roots={"python": ["."]},
        edges=[
            edge("b", "a", 1),
            edge("a", "z", 1),
            edge("a", "b", 9),
            edge("a", "b", 2),
            edge("a", "b", 1, EdgeKind.DYNAMIC),
        ],
        errors=[FileError("b.py", 3, "SyntaxError"), FileError("a.py", None, "OSError")],
    )
    data = json.loads(to_json(result))

    order = [(e["source"], e["target"], e["kind"], e["evidence"]["line"]) for e in data["edges"]]
    assert order == [
        ("a", "b", "dynamic", 1),
        ("a", "b", "import", 2),
        ("a", "b", "import", 9),
        ("a", "z", "import", 1),
        ("b", "a", "import", 1),
    ]
    assert [e["file"] for e in data["errors"]] == ["a.py", "b.py"]


def test_non_ascii_text_is_kept(tmp_path: Path) -> None:
    name = "caf" + chr(0xE9) + ".py"  # "cafe" with an accent, kept ASCII in this file
    (tmp_path / name).write_text("import os\n", encoding="utf-8")
    assert name in _scan(tmp_path)  # ensure_ascii=False keeps the real character
