"""Resolve one Python import to its target module(s) and classify each one.

OWNER-WRITTEN FILE. See AGENTS.md: only the owner implements this logic.
"""

from __future__ import annotations

from repolens.model import ImportClass, Module
from repolens.python.stdlib_names import STDLIB_NAMES  # noqa: F401  (for the owner's use)


def resolve(importer: Module, module: str | None,
            names: list[str], level: int,
            known_modules: set[str]) -> list[tuple[str, ImportClass]]:
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
        has no id of its own in this set.

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
    raise NotImplementedError("resolve() is written by the owner. See AGENTS.md.")
