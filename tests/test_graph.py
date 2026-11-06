"""Phase 2: dependency graph and cycle detection (src/repolens/graph.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from helpers import FIXTURES
from repolens import cli
from repolens.graph import find_cycles, strongly_connected_components
from repolens.model import Edge, EdgeKind, Evidence, ImportClass
from repolens.output import to_json
from repolens.python.analyzer import analyze

CYCLE_PROJECT = FIXTURES / "cycle_project"


def edge(
    source: str,
    target: str,
    classification: ImportClass = ImportClass.LOCAL,
    kind: EdgeKind = EdgeKind.IMPORT,
    line: int = 1,
) -> Edge:
    return Edge(source, target, kind, classification, Evidence(source + ".py", line, "import"))


def cycle_modules(edges: list[Edge]) -> list[tuple[str, ...]]:
    return [cycle.modules for cycle in find_cycles(edges)]


def test_no_cycle_in_a_chain() -> None:
    assert cycle_modules([edge("a", "b"), edge("b", "c")]) == []


def test_simple_cycle() -> None:
    edges = [edge("a", "b"), edge("b", "c"), edge("c", "a")]
    [cycle] = find_cycles(edges)
    assert cycle.modules == ("a", "b", "c")
    assert [(e.source, e.target) for e in cycle.edges] == [("a", "b"), ("b", "c"), ("c", "a")]


def test_self_import_is_a_cycle() -> None:
    [cycle] = find_cycles([edge("a", "a"), edge("a", "b")])
    assert cycle.modules == ("a",)
    assert [(e.source, e.target) for e in cycle.edges] == [("a", "a")]


def test_two_separate_cycles_in_sorted_order() -> None:
    edges = [
        edge("x", "y"),
        edge("y", "x"),
        edge("y", "b"),  # joins the two groups in one direction only: not a cycle
        edge("c", "b"),
        edge("b", "c"),
    ]
    assert cycle_modules(edges) == [("b", "c"), ("x", "y")]


def test_cycle_edges_include_every_edge_inside_and_nothing_outside() -> None:
    edges = [
        edge("a", "b", line=2),
        edge("a", "b", line=1),  # same pair on another line: both are evidence
        edge("b", "a"),
        edge("b", "z"),  # leaves the cycle
    ]
    [cycle] = find_cycles(edges)
    assert [(e.source, e.target, e.evidence.line) for e in cycle.edges] == [
        ("a", "b", 1),
        ("a", "b", 2),
        ("b", "a", 1),
    ]


def test_dynamic_edge_never_creates_a_cycle() -> None:
    edges = [edge("a", "b"), edge("b", "a", kind=EdgeKind.DYNAMIC)]
    assert cycle_modules(edges) == []
    assert cycle_modules([edge("a", "a", kind=EdgeKind.DYNAMIC)]) == []


@pytest.mark.parametrize(
    "classification", [ImportClass.UNRESOLVED, ImportClass.STDLIB, ImportClass.EXTERNAL]
)
def test_non_local_edge_never_creates_a_cycle(classification: ImportClass) -> None:
    edges = [edge("a", "b"), edge("b", "a", classification=classification)]
    assert cycle_modules(edges) == []


def test_same_package_edges_count() -> None:
    edges = [edge("a", "b", kind=EdgeKind.SAME_PACKAGE), edge("b", "a")]
    assert cycle_modules(edges) == [("a", "b")]


def test_5000_module_chain_without_recursion_error() -> None:
    names = [f"m{i:04d}" for i in range(5000)]
    chain = [edge(names[i], names[i + 1]) for i in range(len(names) - 1)]
    assert cycle_modules(chain) == []
    assert len(strongly_connected_components({n: [] for n in names})) == 5000


def test_5000_module_ring_is_one_cycle() -> None:
    names = [f"m{i:04d}" for i in range(5000)]
    ring = [edge(names[i], names[(i + 1) % len(names)]) for i in range(len(names))]
    [cycle] = find_cycles(ring)
    assert cycle.modules == tuple(names)
    assert len(cycle.edges) == 5000


def test_scanning_twice_is_byte_identical_including_cycles() -> None:
    first = to_json(analyze(CYCLE_PROJECT)).encode("utf-8")
    second = to_json(analyze(CYCLE_PROJECT)).encode("utf-8")
    assert first == second
    assert json.loads(first)["cycles"] != []


def test_cycle_project_end_to_end_through_the_cli(tmp_path: Path) -> None:
    target = tmp_path / "graph.json"
    assert cli.main(["scan", str(CYCLE_PROJECT), "-o", str(target)]) == 0
    data = json.loads(target.read_text(encoding="utf-8"))

    assert data["schema_version"] == 2
    # app.d imports app.a but nothing imports app.d back, and its dynamic
    # self-import does not count, so app.d is not in the cycle.
    assert data["cycles"] == [
        {
            "modules": ["app.a", "app.b", "app.c"],
            "edges": [
                {
                    "source": "app.a",
                    "target": "app.b",
                    "kind": "import",
                    "classification": "local",
                    "evidence": {"file": "app/a.py", "line": 1, "text": "from app import b"},
                },
                {
                    "source": "app.b",
                    "target": "app.c",
                    "kind": "import",
                    "classification": "local",
                    "evidence": {"file": "app/b.py", "line": 2, "text": "from app import c"},
                },
                {
                    "source": "app.c",
                    "target": "app.a",
                    "kind": "import",
                    "classification": "local",
                    "evidence": {"file": "app/c.py", "line": 1, "text": "import app.a"},
                },
            ],
        }
    ]
