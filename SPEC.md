# RepoLens Specification

This file says what RepoLens must do. Status and decisions live in PROGRESS.md.

Every requirement has a label:

- [C] Confirmed by the owner.
- [A] Assumption. Needs owner approval before it counts.
- [F] Future. Not part of the current phase.

## 1. Promise

[C] RepoLens helps developers understand and enforce dependency boundaries in Python and Java projects, without writing custom architecture tests and without uploading source code.

## 2. Users and problems

[C] Developers and teams whose projects slowly break their intended layers (controller -> service -> repository) and grow import cycles.

## 3. Non-goals

- [C] No AI.
- [C] No cloud service.
- [C] No account.
- [C] No runtime analysis and no call-graph analysis.
- [C] Static imports only in v1.

## 4. Commands

### Phase 1

- [C] `repolens scan <path> [-o FILE]`
  - Scans the project at `<path>` and writes the JSON output (section 8).
  - Without `-o`, the JSON goes to standard output.
  - With `-o FILE`, the JSON goes to FILE.

### Future

- [F] `repolens check`
- [F] `repolens check --baseline`
- [F] `repolens baseline update`
- [F] `repolens init`

### Exit codes

| Code | Meaning | Label |
| --- | --- | --- |
| 0 | Success. This includes a scan where some files had errors (they are listed in `errors`). | [C] |
| 1 | Rule violations found. Used from Phase 5. | [F] |
| 2 | Bad path, bad arguments, or the `-o` file cannot be written. A clear message goes to stderr. The `-o` folder is checked BEFORE the scan starts, so a bad `-o` fails fast. | [C] |

## 5. Data model

[C] Python and Java both produce these same structures.

| Structure | Fields |
| --- | --- |
| Module | id, language, path |
| Evidence | file, line, text |
| Edge | source, target, kind, classification, evidence |
| Observation | file, line, text, reason |

| Enum | Values |
| --- | --- |
| EdgeKind | `import`, `same_package`, `dynamic` |
| ImportClass | `local`, `stdlib`, `external`, `unresolved` |

- [C] Python module id is the dotted module name, for example `app.auth.service`.
- [C] `path` is repo-relative and uses POSIX `/` separators.
- [C] A package's `__init__.py` gets the package's id. Example: `app/auth/__init__.py` has id `app.auth`.
- [C] Module ids are relative to a source root. A file's id comes from the LONGEST root that contains it. Example: with roots `["src", "."]`, `src/mypkg/x.py` has id `mypkg.x` and `tests/test_x.py` has id `tests.test_x`.
- [C] Shadowed modules: when two files map to the same id, the file under the EARLIER root in the roots list wins (like Python's `sys.path` order). Example: with roots `["src", "."]`, `src/app/x.py` wins over `app/x.py`. The other file is not added to `modules` and is not analysed. It goes into `errors` as `{file, line: null, type: "ShadowedModule"}`.
- [C] Within one root, a package's `__init__.py` wins over a module file with the same id (`app/auth/__init__.py` over `app/auth.py`), as in Python's import system. The module file is reported as `ShadowedModule`.
- [C] Folders and files whose names are not valid Python identifiers (for example `my-scripts/run.py`) are still scanned. Their module id uses the path parts as they are (`my-scripts.run`). Nothing can import them, which is fine.
- [C] `Edge.source` and `Edge.target` are module ids. For `stdlib`, `external` and `unresolved` targets, there is no local module to point to, so the target is the dotted name from the import (see section 7 for from-imports).
- [C] `Evidence.file` is the repo-relative POSIX path of the importing file.
- [C] `Evidence.line` is the first line of the statement (`lineno`). `Evidence.text` is the full statement from `ast.get_source_segment`, with every run of whitespace collapsed to one space.
- [C] `language` is the lowercase string `python` (later `java`).

## 6. Python import classification

[C] Each import is classified by checking these rules in this order. The first rule that matches wins.

1. `local`: the import resolves to a module in the repository.
2. `unresolved`: the top-level name is a local module or package but the module does not exist, or a relative import goes above the source root.
3. `stdlib`: the top-level name is in RepoLens's frozen stdlib list (below).
4. `external`: everything else. Installed packages are never checked, so the output does not depend on the machine.

[C] If the top-level name is a local module or package, the import can only be `local` or `unresolved`, never `stdlib`. This matches real Python, where a local package shadows the stdlib one. Example: with a local `logging/__init__.py` and no `logging/handlers.py`, `import logging.handlers` is `unresolved`.

[C] The stdlib list is frozen in `src/repolens/python/stdlib_names.py`. It is the UNION of the stdlib top-level names for Python 3.10, 3.11, 3.12 and 3.13, so removed modules such as `distutils` and the PEP 594 modules still count as stdlib. `sys.stdlib_module_names` is never used at run time. A test asserts that `set(sys.stdlib_module_names)` is a subset of the frozen list, and CI runs it on every supported Python version.

[C] Classification and resolution are separate steps.

## 7. Python resolution rules

- [C] Source roots: roots = `["src", "."]` if `./src` holds packages or `.py` files AND `src/__init__.py` does not exist, else `["."]`. The order matters: absolute imports try the roots in list order.
- [C] If `src/__init__.py` exists, `src` is a normal package, not a source root. Roots are `["."]`, so `from src.app import x` resolves against `src.app`.
- [C] Every `.py` file in the repository is scanned, including files outside `src/`.
- [C] Absolute imports: `import a.b.c` resolves to the module `a.b.c`.
- [C] Relative imports use the `level` (number of leading dots) to move up from the importer's package.
- [C] `from . import x` inside an `__init__.py` resolves against that package. Example: in `app/auth/__init__.py`, it resolves to `app.auth.x`.
- [C] Local from-imports: `from pkg import name` resolves to `pkg.name` if that is a known module, otherwise to `pkg`.
- [C] Non-local from-imports: the target is the module part only. Example: `from os import path` has target `os`. RepoLens cannot know whether `path` is a submodule without checking the environment.
- [C] Namespace packages (folders without `__init__.py`) count as packages.
- [C] A literal `importlib.import_module("x")` or `__import__("x")` produces a `dynamic` edge. It goes through the same resolver as an absolute import (level 0) to get its classification. Its kind stays `dynamic`.
- [C] A call with a non-literal argument, such as `importlib.import_module(name)`, produces an Observation, never an Edge.
- [C] A relative dynamic import, such as `importlib.import_module(".x", package=__name__)`, produces an Observation with reason `relative dynamic import`. No edge in v1.
- [C] Edges that are identical in every field are removed, so each appears once.

## 8. JSON output v1

- [C] Top-level keys: `schema_version`, `language_roots`, `modules`, `edges`, `observations`, `errors`.
- [C] `schema_version` is the integer `1`.
- [C] `language_roots` maps a language to its list of roots in resolution order, for example `{"python": ["src", "."]}`.
- [C] `modules` are sorted by `id`.
- [C] `edges` are sorted by `(source, target, kind, evidence.line)`.
- [C] `observations` are sorted by `(file, line, reason)`.
- [C] Each entry in `errors` has `file`, `line` (or null) and `type` (for example `SyntaxError`, `UnicodeDecodeError` or `ShadowedModule`). The error message is never stored, because it changes between Python versions. Errors are sorted by `(file, line, type)`.
- [C] No string value in the output contains a backslash. This is checked on the decoded JSON values: in the raw JSON text, a double quote inside evidence text is written as `\"`, and that backslash is only JSON escaping.
- [C] The text is produced with `json.dumps(sort_keys=True, indent=2, ensure_ascii=False)` plus a trailing newline.

### Example

[C] A 3-file project:

```text
app/__init__.py      (empty)
app/repo.py          line 1: import sqlite3
app/service.py       line 1: import os
                     line 2: from app import repo
```

Output of `repolens scan .`:

```json
{
  "edges": [
    {
      "classification": "stdlib",
      "evidence": {
        "file": "app/repo.py",
        "line": 1,
        "text": "import sqlite3"
      },
      "kind": "import",
      "source": "app.repo",
      "target": "sqlite3"
    },
    {
      "classification": "local",
      "evidence": {
        "file": "app/service.py",
        "line": 2,
        "text": "from app import repo"
      },
      "kind": "import",
      "source": "app.service",
      "target": "app.repo"
    },
    {
      "classification": "stdlib",
      "evidence": {
        "file": "app/service.py",
        "line": 1,
        "text": "import os"
      },
      "kind": "import",
      "source": "app.service",
      "target": "os"
    }
  ],
  "errors": [],
  "language_roots": {
    "python": [
      "."
    ]
  },
  "modules": [
    {
      "id": "app",
      "language": "python",
      "path": "app/__init__.py"
    },
    {
      "id": "app.repo",
      "language": "python",
      "path": "app/repo.py"
    },
    {
      "id": "app.service",
      "language": "python",
      "path": "app/service.py"
    }
  ],
  "observations": [],
  "schema_version": 1
}
```

Keys appear in alphabetical order because of `sort_keys=True`.

## 9. Phases

| Phase | Deliverable | Label |
| --- | --- | --- |
| 1 | Scanner, Python AST imports and resolution, deterministic JSON | [C] |
| 2 | Dependency graph and cycle detection | [F] |
| 3 | Java with Tree-sitter, including same-package references | [F] |
| 4 | YAML layers and architecture rules | [F] |
| 5 | `check` command, baseline with fingerprints (rule + source + target + edge kind, never line numbers), GitHub Action | [F] |
| 6 | Self-contained HTML report | [F] |
| 7 | Real-world testing (including TraceX), documentation, release | [F] |

## 10. Phase 1 acceptance criteria

[C] Phase 1 is done when all of these tests pass with `pytest -q`. Tests use small fixture projects in `tests/fixtures/`.

### Scanner, roots, extractor, stdlib list and output

- Scanner: ignored folders are skipped; paths are POSIX and relative; paths are sorted.
- Roots: a flat project gives `["."]`; a src project gives `["src", "."]`; a project with `src/__init__.py` gives `["."]`.
- Module ids: `src/mypkg/x.py` -> `mypkg.x` and `tests/test_x.py` -> `tests.test_x` (longest root wins).
- Shadowed modules: with `src/app/x.py` and `app/x.py`, only `src/app/x.py` is a module; `app/x.py` is a `ShadowedModule` error.
- CLI: a bad `-o` folder exits 2 before the scan starts.
- Extractor:
  - absolute import
  - `from` import
  - relative import with level 1 and level 2
  - function-level import
  - import inside try/except
  - literal `importlib.import_module` gives a `dynamic` edge
  - non-literal `importlib.import_module` gives an Observation
  - a file with a syntax error goes into the errors list, and the scan continues
- Stdlib list: `set(sys.stdlib_module_names)` is a subset of the frozen list.
- Output: scanning the same fixture twice gives byte-identical output; no backslashes in any decoded string value; no absolute paths.

### Resolver (these fail until the owner writes `resolve()`)

- `import app.auth` -> `app/auth.py` or `app/auth/__init__.py` -> local
- `from app import auth`: `app.auth` if that module exists, else `app`
- `from . import x` and `from ..core import y` resolve relative to the importer
- `from . import x` inside `app/auth/__init__.py` -> `app.auth.x`
- a relative import above the root -> unresolved
- src layout: `import mypkg.x` resolves under `src/`
- a namespace package (no `__init__.py`) counts as a package
- a local `logging.py` -> `import logging` is local
- a local `logging` package without `handlers` -> `import logging.handlers` is unresolved
- `import os` -> stdlib
- `import requests` -> external
- `import app.missing` when `app` is local -> unresolved
- with `src/__init__.py`, `from src.app import x` (x is a name, not a module) -> `src.app`

## 11. Open questions

None open. All earlier questions were answered by the owner and are logged in PROGRESS.md (D7 to D19, D32 to D38).

## 12. Known limitations

- [C] SyntaxError line numbers can differ between Python versions for some errors, because the Python parser keeps improving its error reporting. `errors[].line` for a `SyntaxError` is therefore not fully version-independent. The test uses a simple case where all supported versions agree.
