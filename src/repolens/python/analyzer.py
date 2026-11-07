"""Run a full Python scan: find files, extract imports, resolve them.

This module only connects the other steps. The steps themselves live in
scanner.py, roots.py, extractor.py and resolver.py.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Set
from pathlib import Path

from repolens.graph import find_cycles
from repolens.model import Edge, FileError, ImportClass, Module, Observation, ScanResult
from repolens.python import resolver
from repolens.python.extractor import extract_file
from repolens.python.roots import detect_roots, locate
from repolens.scanner import remove_excluded, scan_python_files

LANGUAGE = "python"
SHADOWED_MODULE = "ShadowedModule"

# The shape of resolver.resolve: (importer, module, names, level, known_modules).
ResolveFunction = Callable[
    [Module, str | None, list[str], int, Set[str]], list[tuple[str, ImportClass]]
]


def analyze(
    repo_root: Path,
    resolve_fn: ResolveFunction | None = None,
    exclude: Iterable[str] = (),
) -> ScanResult:
    """Scan the Python project at repo_root.

    exclude holds --exclude patterns (see scanner.remove_excluded). Excluded
    files are removed BEFORE anything else, so they are not modules, do not
    affect root detection, and are never read.

    resolve_fn lets tests use a stand-in resolver. By default the real
    resolver.resolve is used, looked up at call time.
    """
    if resolve_fn is None:
        resolve_fn = resolver.resolve

    files = remove_excluded(scan_python_files(repo_root), exclude)
    roots = detect_roots(files)
    modules, errors = _pick_modules(files, roots)
    # A frozenset, so the resolver can cache work it derives from it (D40).
    known_modules = frozenset(module.id for module in modules)

    edges: set[Edge] = set()  # a set removes exact duplicates (D13)
    observations: list[Observation] = []

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
        # Phase 2: the language-neutral graph step (D46).
        cycles=find_cycles(edges),
    )


def _pick_modules(files: list[str], roots: list[str]) -> tuple[list[Module], list[FileError]]:
    """Give every file a module id. When two files get the same id, keep one.

    The file under the EARLIER root in the roots list wins, like Python's
    sys.path order (D33). Within one root, a package's __init__.py wins over
    a module file with the same id (app/auth/__init__.py over app/auth.py),
    as in Python's import system (D34). The losing file is not a module: it
    is reported as a ShadowedModule error and is not analysed.
    """
    candidates: dict[str, list[tuple[tuple[int, int, str], str]]] = {}
    for path in files:
        root, mod_id = locate(path, roots)
        is_package = path == "__init__.py" or path.endswith("/__init__.py")
        rank = (roots.index(root), 0 if is_package else 1, path)
        candidates.setdefault(mod_id, []).append((rank, path))

    modules: list[Module] = []
    errors: list[FileError] = []
    for mod_id, entries in candidates.items():
        entries.sort()
        modules.append(Module(mod_id, LANGUAGE, entries[0][1]))
        for _, shadowed_path in entries[1:]:
            errors.append(FileError(shadowed_path, None, SHADOWED_MODULE))
    modules.sort(key=lambda module: module.path)  # analyse files in path order
    return modules, errors
