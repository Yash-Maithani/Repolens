"""Turn a ScanResult into deterministic JSON (SPEC.md section 8).

Deterministic means: the same project always gives exactly the same bytes,
on any machine. That is why every list is sorted here, keys are sorted by
json.dumps, and nothing like a timestamp or an absolute path is written.
"""

from __future__ import annotations

import json
from typing import Any

from repolens.model import Edge, FileError, Module, Observation, ScanResult


def to_dict(result: ScanResult) -> dict[str, Any]:
    return {
        "schema_version": result.schema_version,
        "language_roots": {lang: list(roots) for lang, roots in result.language_roots.items()},
        "modules": [_module(m) for m in sorted(result.modules, key=_module_key)],
        "edges": [_edge(e) for e in sorted(result.edges, key=_edge_key)],
        "observations": [
            _observation(o) for o in sorted(result.observations, key=_observation_key)
        ],
        "errors": [_error(e) for e in sorted(result.errors, key=_error_key)],
    }


def to_json(result: ScanResult) -> str:
    text = json.dumps(to_dict(result), sort_keys=True, indent=2, ensure_ascii=False)
    return text + "\n"


# Sort keys. Each one starts with the order from SPEC.md section 8; the extra
# fields at the end only break ties, so the order is always total.


def _module_key(m: Module) -> tuple:
    return (m.id, m.path)


def _edge_key(e: Edge) -> tuple:
    return (
        e.source,
        e.target,
        e.kind.value,
        e.evidence.line,
        e.classification.value,
        e.evidence.file,
        e.evidence.text,
    )


def _observation_key(o: Observation) -> tuple:
    return (o.file, o.line, o.reason, o.text)


def _error_key(e: FileError) -> tuple:
    # A missing line (None) sorts before any number.
    return (e.file, e.line is not None, e.line or 0, e.type)


def _module(m: Module) -> dict[str, Any]:
    return {"id": m.id, "language": m.language, "path": m.path}


def _edge(e: Edge) -> dict[str, Any]:
    return {
        "source": e.source,
        "target": e.target,
        "kind": e.kind.value,
        "classification": e.classification.value,
        "evidence": {"file": e.evidence.file, "line": e.evidence.line, "text": e.evidence.text},
    }


def _observation(o: Observation) -> dict[str, Any]:
    return {"file": o.file, "line": o.line, "text": o.text, "reason": o.reason}


def _error(e: FileError) -> dict[str, Any]:
    return {"file": e.file, "line": e.line, "type": e.type}
