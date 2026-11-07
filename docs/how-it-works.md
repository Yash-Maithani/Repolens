# How RepoLens works

A short guide for reading the code. Every example below comes from a real test.

## 1. The resolver in 6 steps

File: `src/repolens/python/resolver.py`. The resolver gets one import and returns where it points and what kind of target it is.

**Step 1. Collect the local names.** Take every module id in the repository and add every package above it. This is how a folder without `__init__.py` (a namespace package) still counts as a package.

- Files `main.py`, `ns/mod.py` -> local names `main`, `ns`, `ns.mod`.
- So `from ns import mod` -> `("ns.mod", local)` (test `test_namespace_package_counts_as_package`).

**Step 2. Absolute or relative?** If the import has no leading dots (`level` is 0), the module part is already the full name. Go to step 5.

- `import app.auth` -> name `app.auth`.

**Step 3. Find the importer's package.** For a normal file, drop the last part of its id. An `__init__.py` is its own package.

- `app/auth/service.py` (id `app.auth.service`) -> package `app.auth`.
- `app/auth/__init__.py` (id `app.auth`) -> package `app.auth`, so `from . import x` -> `("app.auth.x", local)` (test `test_from_dot_import_inside_init_uses_that_package`).

**Step 4. Go up one package for each extra dot.** One dot means "this package", two dots mean "the parent". Then add the module part, if there is one. If the dots climb past the top, the import is unresolved.

- `from ..core import y` in `app/auth/service.py`: `app.auth` -> up one -> `app`, add `core` -> `app.core` (test `test_from_dot_dot_core_import_resolves_two_levels_up`).
- `from ... import x` in `app/service.py`: package `app`, three dots need two steps up, but only one part exists -> `unresolved` (test `test_relative_import_above_root_is_unresolved`).

**Step 5. Handle each name of a from-import.** Try `base.name`. If that is a local module, use it. Otherwise the name is something defined inside `base` (a function or a class), so use `base`.

- `from app import auth` with `app/auth.py` -> `("app.auth", local)` (test `test_from_package_import_existing_module`).
- `from app import auth` with only `app/other.py` -> `("app", local)` (test `test_from_package_import_name_that_is_not_a_module`).
- `from os import path` -> `os.path` is not local, so use `os` -> `("os", stdlib)` (test `test_from_non_local_module_uses_module_part_only`).

**Step 6. Classify the name.** Check in this order and stop at the first match: local, unresolved, stdlib, external.

- `import app.missing` while `app` is local -> `unresolved` (test `test_import_missing_module_of_local_package_is_unresolved`).
- `import os` -> `stdlib` (test `test_import_os_is_stdlib`).
- `import requests` -> `external` (test `test_import_requests_is_external`).

## 2. Why the order is local, unresolved, stdlib, external

- **Local first.** Python looks in your project before the standard library. A file `logging.py` in your project hides the real `logging` module. So `import logging` is local (test `test_local_logging_module_wins_over_stdlib`).
- **Unresolved second.** If the first part of the name is yours, Python will never look in the standard library for the rest. With a local `logging/` package and no `logging/handlers.py`, `import logging.handlers` fails at runtime. Calling it stdlib would hide a real bug, so it is unresolved (test `test_local_logging_package_without_handlers_is_unresolved`).
- **Stdlib third.** The name is not ours, and it is in the frozen stdlib list. The list is frozen so the answer is the same on every Python version.
- **External last.** Everything else. RepoLens never checks what is installed, so the result never depends on the machine.

## 3. Tarjan's algorithm, step by step

File: `src/repolens/graph.py`. Example: `a -> b -> c -> a` (test `test_simple_cycle`).

The algorithm walks the graph once. For each module it remembers two numbers:

- **index**: the order in which the module was first visited.
- **low**: the smallest index this module can reach through modules that are still open (on the stack).

When a module is finished and its `low` equals its own `index`, it is the start of a group. Every module above it on the stack belongs to that group.

| Step | What happens | index | low | Stack |
| --- | --- | --- | --- | --- |
| 1 | Visit `a` | a=0 | a=0 | a |
| 2 | `a` points to `b`, not visited yet: visit `b` | b=1 | b=1 | a, b |
| 3 | `b` points to `c`, not visited yet: visit `c` | c=2 | c=2 | a, b, c |
| 4 | `c` points to `a`, which is on the stack: a loop. `low[c] = min(2, index[a]=0)` | | c=0 | a, b, c |
| 5 | `c` is finished. `low[c]=0` is not `index[c]=2`, so `c` is not a start. Pass it up: `low[b] = min(1, 0)` | | b=0 | a, b, c |
| 6 | `b` is finished. `low[b]=0` is not `index[b]=1`. Pass it up: `low[a] = min(0, 0)` | | a=0 | a, b, c |
| 7 | `a` is finished. `low[a]=0` equals `index[a]=0`: `a` starts a group. Pop until `a` | | | (empty) |

Result: one group `{a, b, c}`. It has more than one module, so it is a cycle.

Why no recursion: the usual version calls itself once per module along a path. Python stops at about 1000 nested calls. RepoLens keeps its own list of "where was I" entries instead, so a chain of 5000 modules works (test `test_5000_module_chain_without_recursion_error`).

## 4. Read the code in this order

1. `src/repolens/model.py`: the data structures everything else uses.
2. `src/repolens/scanner.py`: finds the `.py` files.
3. `src/repolens/python/roots.py`: source roots and module ids.
4. `src/repolens/python/extractor.py`: reads the imports from one file.
5. `src/repolens/python/resolver.py`: section 1 of this guide.
6. `src/repolens/python/analyzer.py`: connects the steps above into one scan.
7. `src/repolens/graph.py`: section 3 of this guide.
8. `src/repolens/output.py`: turns the result into sorted JSON.
9. `src/repolens/cli.py`: the `repolens scan` command.
10. `tests/test_resolver.py` and `tests/test_graph.py`: the examples used in this guide.
