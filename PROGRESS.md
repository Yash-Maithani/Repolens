# Progress

Status words: Planned, In progress, Implemented, Tested, Released.

## Current milestone

Phase 1: Scanner, Python AST imports and resolution, deterministic JSON.

Status: In progress

Note: CI will fail on the resolver tests until the owner writes `resolve()`. This is expected and accepted. The owner will not open the Phase 1 pull request until the resolver passes.

## Phase status

| Phase | Deliverable | Status |
| --- | --- | --- |
| 1 | Scanner, Python AST imports and resolution, deterministic JSON | In progress |
| 2 | Dependency graph and cycle detection | Planned |
| 3 | Java with Tree-sitter, including same-package references | Planned |
| 4 | YAML layers and architecture rules | Planned |
| 5 | `check` command, baseline with fingerprints, GitHub Action | Planned |
| 6 | Self-contained HTML report | Planned |
| 7 | Real-world testing, documentation, release | Planned |

## Decision log

| ID | Decision | Reason |
| --- | --- | --- |
| D1 | Phase 1 uses the Python standard library only, plus pytest for tests. | Fewer dependencies, easier install, nothing to audit. |
| D2 | One `external` class. RepoLens never checks which packages are installed. | Determinism: the output must not depend on the machine. |
| D3 | Local resolution wins over stdlib names. | A project file such as `logging.py` shadows the stdlib module at runtime, so the project file is the real dependency. |
| D4 | Source roots are `["src"]` if `./src` holds packages or `.py` files, else `["."]`. Replaced by D9. | Supports both the src layout and the flat layout with one simple rule. |
| D5 | MIT license. | Simple, permissive and widely understood. |
| D6 | The owner writes `src/repolens/python/resolver.py`. | The resolver is the core learning goal of Phase 1. |
| D7 | Classification order is local -> unresolved -> stdlib -> external. A local top-level name can only give local or unresolved. | Matches real Python, where a local package shadows the stdlib one. Fixes the `logging.handlers` case. |
| D8 | The stdlib list is frozen in `stdlib_names.py`: the union of Python 3.10 to 3.13. A test checks `sys.stdlib_module_names` is a subset. CI runs Python 3.10, 3.11, 3.12 and 3.13. | The output must not change with the Python version that runs RepoLens. |
| D9 | Roots are `["src", "."]` when `./src` qualifies, else `["."]`. Every `.py` file is scanned. A module id comes from the longest root that contains the file. Absolute imports try roots in list order. | Files outside `src/` (tests, scripts) are part of the project and need ids. |
| D10 | Errors store file, line and error type only, never the message. | Error messages change between Python versions. |
| D11 | Red CI on the resolver tests is accepted until `resolve()` exists. The owner opens the Phase 1 pull request only after the resolver passes. | The resolver is owner-written (D6), and tests must not be skipped. |
| D12 | Multi-line imports: evidence line is the statement's first line; text is the full statement from `ast.get_source_segment` with whitespace runs collapsed to one space. | Shows the whole import and stays on one line. |
| D13 | Edges that are identical in every field are removed. | Avoids noise without losing information. |
| D14 | Literal dynamic imports go through `resolve()` as absolute imports (level 0) to get a classification. Their kind stays `dynamic`. | One classification path for all imports, while keeping dynamic evidence separate. |
| D15 | `importlib.import_module(".x", package=...)` is recorded as an Observation with reason `relative dynamic import`. No edge in v1. | Resolving it needs the runtime value of `package`. |
| D16 | Folders and files with non-identifier names (for example `my-scripts`) are scanned. The module id uses the path parts as they are. | Every file is visible in the output, even if nothing can import it. |
| D17 | If the `-o` file cannot be written, exit 2 with a clear message on stderr. | Same exit code as other user input problems. |
| D18 | Non-local from-imports use the module part as the target (`from os import path` -> `os`). Local from-imports keep `pkg.name` if known, else `pkg`. | Checking whether a non-local name is a submodule would need the environment. |
| D19 | Observations sort by `(file, line, reason)`. Errors sort by `(file, line, type)`. | Deterministic output. |
| D20 | A small `python/analyzer.py` connects scanner, roots, extractor and resolver. `analyze()` takes an optional `resolve_fn`; tests that are not about resolution pass a stand-in resolver (`tests/helpers.py`). | Lets scanner, extractor, output and CLI be tested before `resolve()` exists, without skipping anything. |
| D21 | `model.py` adds two structures that SPEC.md section 5 does not list: `FileError(file, line, type)` and `ScanResult`. The extractor has its own `RawImport` record (the import as written, before resolution). | The `errors` list needs a shape, and resolution needs a clear input. |
| D22 | `detect_roots()` returns roots in resolution order (`["src", "."]`), not alphabetical order. | D9 says absolute imports try roots in list order, and alphabetical order would put "." first. |
| D23 | A root's own `__init__.py` (for example `src/__init__.py`) falls back to the next shorter root (id `src`). A top-level `./__init__.py` gets id `__init__`. Since D35, `src` is never a root when `src/__init__.py` exists, so the fallback only matters for `./__init__.py`. | Every file needs a non-empty id. |
| D24 | The scanner skips symbolic links to files as well as to folders. | A link can point outside the repository. |
| D25 | Dynamic imports are detected only as `importlib.import_module(...)` and `__import__(...)`, written with those exact names. A first argument that is not a non-empty string literal gives a `non-literal dynamic import` Observation. `__import__` with a level other than a literal 0 gives a `relative dynamic import` Observation. Evidence text for a dynamic import is the call expression. | Simple and predictable. Aliases such as `from importlib import import_module` would need name tracking. |
| D26 | The error `type` is the exception class name (`SyntaxError`, `IndentationError`, `TabError`, `UnicodeDecodeError`, `OSError`). A file with null bytes is reported as `SyntaxError` with line null on every Python version. Files with errors are still listed in `modules`. | Python 3.10 and 3.11 raise ValueError for null bytes, 3.12+ raise SyntaxError. |
| D27 | Sorting adds tie-breakers after the SPEC.md keys: edges by classification, evidence file and text; observations by text; errors with a null line first; modules by path. | The SPEC.md keys alone do not give a total order. |
| D28 | The CLI writes UTF-8 bytes (to `sys.stdout.buffer` or with `write_bytes`). | On Windows, text mode would turn `\n` into `\r\n` and may use a non-UTF-8 encoding. |
| D29 | The frozen stdlib list comes from CPython's `Python/stdlib_module_names.h` on the 3.10 to 3.13 branches (321 names, including private `_names`, as in `sys.stdlib_module_names`). The 3.11 list matched the running interpreter exactly. | Built from the source CPython itself uses, not from memory. |
| D30 | Test layout: the scanner test builds ignored folders in a temporary folder; `tests/fixtures` is excluded from pytest collection; the "no backslashes" test checks decoded JSON values, not raw text. | `.gitignore` would drop committed `.venv`/`build` fixtures; fixtures contain `test_*.py` and broken files; raw JSON writes a quote as `\"`. |
| D31 | CI uses `fail-fast: false` and runs on every push and pull request. | A failure on one Python version must not hide results on the others. |
| D32 | Owner approved: the "no backslashes" check runs on decoded JSON string values, not on the raw text. | Raw JSON writes a double quote as `\"`; that backslash is escaping, not data. |
| D33 | Owner decision: when two files map to the same module id, the file under the earlier root in the roots list wins. The other file is not a module, is not analysed, and is reported as `{file, line: null, type: "ShadowedModule"}`. | Same as Python's `sys.path` order. |
| D34 | Assumption, needs owner approval: within one root, a package's `__init__.py` wins over a module file with the same id (`app/auth/__init__.py` over `app/auth.py`). | Python's import system prefers the package folder. D33 does not cover two files under the same root, and the output needs one rule. |
| D35 | Owner decision: `./src` is a source root only if `src/__init__.py` does not exist. Otherwise `src` is a normal package and roots are `["."]`. | Projects that import `from src.app import x` would otherwise be unresolved. |
| D36 | Owner decision: the CLI checks the `-o` parent folder before scanning and exits 2 if it does not exist. I also added an exit 2 when `-o` points at an existing folder. A write error after the scan is still exit 2. | A typo in `-o` should not cost a full scan. |
| D37 | Owner decision: SyntaxError line numbers can differ between Python versions. Accepted as a known limitation (SPEC.md section 12, README.md). The test keeps a simple case. | The Python parser keeps improving its error positions. |
| D38 | Owner decision: `.gitattributes` with `* text=auto eol=lf`. Renormalizing changed no files (the index was already LF). | Fixtures and expected JSON must have LF on every machine, including Windows CI checkouts. |

## Verification log

| Date | Command | Result |
| --- | --- | --- |
| 2026-11-06 | `pytest -q` (Python 3.11.9, Windows) | 49 passed, 20 failed. All 20 failures are in `tests/test_resolver.py` and are the `NotImplementedError` from the resolver stub (expected, D11). |
| 2026-11-06 | `pytest -q` (Python 3.11.9, Windows), after D32 to D38 | 54 passed, 21 failed. All 21 failures are in `tests/test_resolver.py` and are the `NotImplementedError` from the resolver stub (expected, D11). |
