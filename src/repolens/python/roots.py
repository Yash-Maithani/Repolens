"""Source root detection and module ids (SPEC.md sections 5 and 7, decision D9)."""

from __future__ import annotations


def detect_roots(py_files: list[str]) -> list[str]:
    """Return the source roots, in the order absolute imports try them.

    py_files is the scanner's list of repo-relative POSIX paths. If any .py
    file lives under ./src (directly, or inside a package or namespace
    package), the roots are ["src", "."]. Otherwise they are ["."].

    Exception (D35): if src/__init__.py exists, src is a normal package, not
    a source root. The roots are then ["."], so `from src.app import x`
    resolves against the module ids "src", "src.app" and so on.

    The list is in resolution order, not alphabetical order: "src" comes
    first because absolute imports try it first.
    """
    if "src/__init__.py" in py_files:
        return ["."]
    if any(path.startswith("src/") for path in py_files):
        return ["src", "."]
    return ["."]


def module_id(path: str, roots: list[str]) -> str:
    """Return the dotted module id for a repo-relative .py path.

    The id comes from the LONGEST root that contains the file, so with roots
    ["src", "."], "src/mypkg/x.py" is "mypkg.x" and "tests/test_x.py" is
    "tests.test_x". A package's __init__.py gets the package's id.

    Path parts are used as they are, even if they are not valid Python
    identifiers ("my-scripts/run.py" -> "my-scripts.run").
    """
    return locate(path, roots)[1]


def locate(path: str, roots: list[str]) -> tuple[str, str]:
    """Return (root, module id) for a repo-relative .py path.

    The root is the one the id was taken from. The analyzer uses it to decide
    which file wins when two files get the same id (D33).
    """
    for root in sorted(roots, key=_root_length, reverse=True):
        if root == "." or path.startswith(root + "/"):
            relative = path if root == "." else path[len(root) + 1 :]
            parts = _module_parts(relative)
            if parts:
                return root, ".".join(parts)
            # The file is the root's own __init__.py, so it has no id under
            # this root. Try the next, shorter root.
    # Only a top-level ./__init__.py reaches this point.
    return ".", "__init__"


def _root_length(root: str) -> int:
    return 0 if root == "." else len(root)


def _module_parts(relative: str) -> list[str]:
    parts = relative[: -len(".py")].split("/")
    if parts[-1] == "__init__":
        parts.pop()
    return parts
