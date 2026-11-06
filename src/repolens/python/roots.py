"""Source root detection and module ids (SPEC.md sections 5 and 7, decision D9)."""

from __future__ import annotations


def detect_roots(py_files: list[str]) -> list[str]:
    """Return the source roots, in the order absolute imports try them.

    py_files is the scanner's list of repo-relative POSIX paths. If any .py
    file lives under ./src (directly, or inside a package or namespace
    package), the roots are ["src", "."]. Otherwise they are ["."].

    The list is in resolution order, not alphabetical order: "src" comes
    first because absolute imports try it first.
    """
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
    for root in sorted(roots, key=_root_length, reverse=True):
        if root == "." or path.startswith(root + "/"):
            relative = path if root == "." else path[len(root) + 1 :]
            parts = _module_parts(relative)
            if parts:
                return ".".join(parts)
            # The file is the root's own __init__.py (for example
            # src/__init__.py). It has no id under this root, so try the
            # next, shorter root.
    # Only a top-level ./__init__.py reaches this point.
    return "__init__"


def _root_length(root: str) -> int:
    return 0 if root == "." else len(root)


def _module_parts(relative: str) -> list[str]:
    parts = relative[: -len(".py")].split("/")
    if parts[-1] == "__init__":
        parts.pop()
    return parts
