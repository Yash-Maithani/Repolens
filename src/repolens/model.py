"""The language-neutral data model (SPEC.md section 5).

Python and Java analysis both produce these structures. All dataclasses are
frozen: once created, a value never changes. Frozen dataclasses are also
hashable, so they can be put in a set (used to remove duplicate edges).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EdgeKind(Enum):
    """How a dependency was found."""

    IMPORT = "import"
    SAME_PACKAGE = "same_package"
    DYNAMIC = "dynamic"


class ImportClass(Enum):
    """Where the imported module lives."""

    LOCAL = "local"
    STDLIB = "stdlib"
    EXTERNAL = "external"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class Module:
    """One source file in the repository."""

    id: str  # dotted module name, for example "app.auth.service"
    language: str  # "python" (later "java")
    path: str  # repo-relative POSIX path, for example "app/auth/service.py"


@dataclass(frozen=True)
class Evidence:
    """Where in the source a dependency was found."""

    file: str  # repo-relative POSIX path
    line: int  # first line of the statement
    text: str  # the statement, whitespace collapsed


@dataclass(frozen=True)
class Edge:
    """A dependency from one module to another."""

    source: str
    target: str
    kind: EdgeKind
    classification: ImportClass
    evidence: Evidence


def edge_sort_key(edge: Edge) -> tuple:
    """The one sort order for edges, used by graph.py and output.py.

    It starts with the SPEC.md order (source, target, kind, evidence.line);
    the remaining fields only break ties, so the order is always total (D27).
    """
    return (
        edge.source,
        edge.target,
        edge.kind.value,
        edge.evidence.line,
        edge.classification.value,
        edge.evidence.file,
        edge.evidence.text,
    )


@dataclass(frozen=True)
class Observation:
    """Something worth reporting that is not an edge (for example a non-literal dynamic import)."""

    file: str
    line: int
    text: str
    reason: str


@dataclass(frozen=True)
class FileError:
    """A file that could not be analysed. Only the error type is stored, never the message (D10)."""

    file: str
    line: int | None
    type: str


@dataclass(frozen=True)
class Cycle:
    """A group of modules that depend on each other in a loop (SPEC.md section 8).

    modules: the module ids in the cycle, sorted.
    edges: the counted local edges whose source and target are both in the cycle.
    """

    modules: tuple[str, ...]
    edges: tuple[Edge, ...]


@dataclass(frozen=True)
class ScanResult:
    """Everything one scan produces. output.py turns this into JSON."""

    language_roots: dict[str, list[str]]
    modules: list[Module] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    errors: list[FileError] = field(default_factory=list)
    cycles: list[Cycle] = field(default_factory=list)
    schema_version: int = 2
