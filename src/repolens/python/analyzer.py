"""Run a full Python scan: find files, extract imports, resolve them.

This module only connects the other steps. The steps themselves live in
scanner.py, roots.py, extractor.py and resolver.py.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from repolens.model import Edge, FileError, ImportClass, Module, Observation, ScanResult
from repolens.python import resolver
from repolens.python.extractor import extract_file
from repolens.python.roots import detect_roots, module_id
from repolens.scanner import scan_python_files

LANGUAGE = "python"

# The shape of resolver.resolve: (importer, module, names, level, known_modules).
ResolveFunction = Callable[
    [Module, str | None, list[str], int, set[str]], list[tuple[str, ImportClass]]
]


def analyze(repo_root: Path, resolve_fn: ResolveFunction | None = None) -> ScanResult:
    """Scan the Python project at repo_root.

    resolve_fn lets tests use a stand-in resolver. By default the owner's
    resolver.resolve is used, looked up at call time.
    """
    if resolve_fn is None:
        resolve_fn = resolver.resolve

    files = scan_python_files(repo_root)
    roots = detect_roots(files)
    modules = [Module(module_id(path, roots), LANGUAGE, path) for path in files]
    known_modules = {module.id for module in modules}

    edges: set[Edge] = set()  # a set removes exact duplicates (D13)
    observations: list[Observation] = []
    errors: list[FileError] = []

    for importer in modules:
        extracted = extract_file(repo_root, importer.path)
        if extracted.error is not None:
            errors.append(extracted.error)
            continue
        observations.extend(extracted.observations)
        for raw in extracted.imports:
            targets = resolve_fn(importer, raw.module, list(raw.names), raw.level, known_modules)
            for target, classification in targets:
                edges.add(Edge(importer.id, target, raw.kind, classification, raw.evidence))

    return ScanResult(
        language_roots={LANGUAGE: roots},
        modules=modules,
        edges=list(edges),
        observations=observations,
        errors=errors,
    )
