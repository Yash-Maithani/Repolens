"""Resolve one Python import to its target module(s) and classify each one.

Written by the agent at the owner's request (PROGRESS.md D39). A walkthrough
with examples is in docs/how-it-works.md.

The work is split into two separate steps (SPEC.md section 6):
1. RESOLUTION: turn the import into an absolute dotted name, for example
   `from ..core import db` inside app/auth/service.py -> "app.core.db".
2. CLASSIFICATION: decide what kind of name that is: local, unresolved,
   stdlib or external.
"""

from __future__ import annotations

from collections.abc import Set
from functools import lru_cache

from repolens.model import ImportClass, Module
from repolens.python.stdlib_names import STDLIB_NAMES


def resolve(importer: Module, module: str | None,
            names: list[str], level: int,
            known_modules: Set[str]) -> list[tuple[str, ImportClass]]:
    """Resolve one import and classify every target it produces.

    Parameters
    ----------
    importer:
        The module that contains the import. importer.id is its dotted id
        (for example "app.auth.service") and importer.path its repo-relative
        POSIX path. If importer.path ends with "/__init__.py" (or is
        "__init__.py"), the importer IS a package, which matters for
        relative imports.
    module:
        The module part of the import, as written, without leading dots.
        `import a.b` -> "a.b". `from a.b import c` -> "a.b".
        `from ..core import y` -> "core". `from . import x` -> None.
    names:
        The imported names of a from-import, in order. Empty for a plain
        `import a.b` and for dynamic imports. `from x import *` gives ["*"].
    level:
        The number of leading dots. 0 for absolute imports and for dynamic
        imports (literal importlib.import_module / __import__ calls are
        always passed in as level 0).
    known_modules:
        The ids of all modules in the repository, already relative to their
        source root (src/mypkg/x.py has id "mypkg.x"). Every id is backed by
        a real .py file. A namespace package (a folder without __init__.py)
        has no id of its own in this set. The type is collections.abc.Set,
        so both a set and a frozenset are correct (D49). The analyzer passes
        a frozenset because it is faster (see _local_names).

    Returns
    -------
    A list of (target, classification) pairs. A from-import with several
    names may produce several pairs; the caller removes exact duplicates.

    Classification (SPEC.md section 6), checked in this order:
    1. LOCAL: the import resolves to a module in the repository.
    2. UNRESOLVED: the top-level name is a local module or package but the
       module does not exist, or a relative import goes above the source
       root. If the top-level name is local, the result can only be LOCAL or
       UNRESOLVED, never STDLIB (a local package shadows the stdlib one).
    3. STDLIB: the top-level name is in STDLIB_NAMES (the frozen list in
       stdlib_names.py). Never use sys.stdlib_module_names.
    4. EXTERNAL: everything else. Installed packages are never checked.
    Classification and resolution are separate steps.

    Resolution (SPEC.md section 7):
    - Absolute: `import a.b.c` resolves to "a.b.c".
    - Relative: `level` moves up from the importer's package. For a normal
      module the package is its id without the last part; for an
      __init__.py the package is its own id. Going above the root is
      UNRESOLVED.
    - `from . import x` inside app/auth/__init__.py resolves to "app.auth.x".
    - Local from-imports: `from pkg import name` resolves to "pkg.name" if
      that is a known module, otherwise to "pkg".
    - Non-local from-imports: the target is the module part only.
      `from os import path` has target "os", because RepoLens cannot know
      whether `path` is a submodule without checking the environment.
    - Namespace packages (folders without __init__.py) count as packages.
    - Roots: the ids in known_modules are already root-relative, so a plain
      dotted lookup works for both the flat and the src layout. Shadowed
      files (D33) are already removed: each id in known_modules belongs to
      exactly one file.
    - src as a package: if src/__init__.py exists, src is a normal package
      and the roots are ["."]. Then ids start with "src." and
      `from src.app import x` resolves against "src.app" (D35).
    - For STDLIB, EXTERNAL and UNRESOLVED results, the target is the dotted
      name from the import (module part only for from-imports).

    Examples (assume known_modules = {"app", "app.auth", "app.core.db"}):
    - `import os`                    -> [("os", STDLIB)]
    - `import requests`              -> [("requests", EXTERNAL)]
    - `import app.auth`              -> [("app.auth", LOCAL)]
    - `import app.missing`           -> [("app.missing", UNRESOLVED)]
    - `from app import auth`         -> [("app.auth", LOCAL)]
    - `from app import helper`       -> [("app", LOCAL)]
    """
    local_names = _local_names(frozenset(known_modules))

    # --- Step 1: RESOLUTION. Turn the import into an absolute dotted name. ---
    if level > 0:
        base = relative_base(importer, module, level)
        if base is None:
            # The dots climb above the source root. Python itself would fail
            # here ("attempted relative import beyond top-level package").
            # We keep the import as written, for example "...x".
            written = "." * level + (module or "")
            return [(written, ImportClass.UNRESOLVED)]
    else:
        # An absolute import always has a module part (`import x` or
        # `from x import y`), so `module` is not None here.
        base = module or ""

    # --- Step 2: CLASSIFICATION, done per target. ---
    if not names:
        # A plain `import a.b.c`, or a dynamic import: one target.
        return [(base, classify(base, local_names))]

    # A from-import: every imported name may point somewhere different.
    results: list[tuple[str, ImportClass]] = []
    for name in names:
        pair = resolve_from_name(base, name, local_names)
        if pair not in results:  # `from app import a, b` may give "app" twice
            results.append(pair)
    return results


def importer_package(importer: Module) -> list[str]:
    """Return the package that contains the importer, as a list of parts.

    For a normal module the package is its id without the last part:
        app/auth/service.py (id "app.auth.service") -> ["app", "auth"]
    An __init__.py IS its package, so nothing is removed:
        app/auth/__init__.py (id "app.auth")        -> ["app", "auth"]
    A top-level module has no package:
        main.py (id "main")                          -> []
    """
    if importer.path == "__init__.py":
        # The repository's own top-level __init__.py: it sits at the root,
        # so it has no package above it (its id is "__init__", see D23).
        return []
    parts = importer.id.split(".")
    if importer.path.endswith("/__init__.py"):
        return parts
    return parts[:-1]


def go_up(package: list[str], level: int) -> list[str] | None:
    """Apply the leading dots of a relative import to a package.

    One dot means "this package", two dots mean "the parent package", and so
    on, so we remove (level - 1) parts from the end.
        go_up(["app", "auth"], 1) -> ["app", "auth"]
        go_up(["app", "auth"], 2) -> ["app"]
        go_up(["app", "auth"], 3) -> None   (above the root)
    Returns None when nothing would be left: a relative import can never
    reach the root itself, because the root is not a package (D41).
    """
    steps_up = level - 1
    if steps_up >= len(package):
        return None
    return package[: len(package) - steps_up]


def relative_base(importer: Module, module: str | None, level: int) -> str | None:
    """Turn a relative import into an absolute dotted name, or None if it is above the root.

        `from . import x`      in app/service.py      -> "app"
        `from ..core import y` in app/auth/service.py -> "app.core"
    """
    package = go_up(importer_package(importer), level)
    if package is None:
        return None
    if module:
        # `from ..core import y`: add "core" after the package we reached.
        package = package + module.split(".")
    return ".".join(package)


def resolve_from_name(base: str, name: str, local_names: frozenset[str]) -> tuple[str, ImportClass]:
    """Resolve one name of `from base import name`.

    Local rule: if base.name is a module (or package) in the repository, the
    import points to it. Otherwise `name` is something defined inside base
    (a function, class or variable), so the import points to base itself.
        from app import auth   (app/auth.py exists)  -> "app.auth"
        from app import helper (no such module)      -> "app"

    Non-local rule (D18): for stdlib and external modules we cannot know
    whether `name` is a submodule, so the target is always base:
        from os import path -> "os"
    `from x import *` never matches a module, so it also gives base.
    """
    candidate = base + "." + name
    if candidate in local_names:
        return candidate, ImportClass.LOCAL
    return base, classify(base, local_names)


def classify(name: str, local_names: frozenset[str]) -> ImportClass:
    """Classify an absolute dotted name. The ORDER of the checks matters (D7)."""
    # 1. LOCAL: the name is a module or package in this repository.
    if name in local_names:
        return ImportClass.LOCAL

    top_level = name.split(".")[0]  # "app.missing" -> "app"

    # 2. UNRESOLVED: the first part is ours, but the rest does not exist.
    #    This check comes BEFORE stdlib on purpose: a local `logging`
    #    package hides the stdlib one, so `import logging.handlers` cannot
    #    be the stdlib module here, it is a broken local import.
    if top_level in local_names:
        return ImportClass.UNRESOLVED

    # 3. STDLIB: the frozen list, never sys.stdlib_module_names (D8).
    if top_level in STDLIB_NAMES:
        return ImportClass.STDLIB

    # 4. EXTERNAL: everything else. We never check what is installed (D2).
    return ImportClass.EXTERNAL


@lru_cache(maxsize=8)
def _local_names(known_modules: frozenset[str]) -> frozenset[str]:
    """Return every local module id PLUS every package above it.

        {"app.core.db"} -> {"app", "app.core", "app.core.db"}

    Adding the packages is what makes namespace packages work: a folder
    without __init__.py has no id in known_modules, but its name appears
    here because a module lives inside it.

    Why the cache: resolve() runs once per import, and building this set
    looks at every module, so without a cache a big repository would build
    it thousands of times. lru_cache can only remember hashable arguments.
    A frozenset is hashable and Python stores its hash after computing it
    once, so when the analyzer passes the same frozenset on every call, the
    lookup is instant and the set is built only once per scan.
    """
    names: set[str] = set()
    for module_id in known_modules:
        parts = module_id.split(".")
        # For "app.core.db" add "app", "app.core" and "app.core.db".
        for length in range(1, len(parts) + 1):
            names.add(".".join(parts[:length]))
    return frozenset(names)
