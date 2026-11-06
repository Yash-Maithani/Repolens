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

## Verification log

| Date | Command | Result |
| --- | --- | --- |
