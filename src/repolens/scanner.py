"""Find the Python files in a repository.

The scanner walks the folder tree with pathlib. It never follows symbolic
links, because a link can point outside the repository and make the output
depend on the machine.
"""

from __future__ import annotations

from pathlib import Path

# Folder names that never contain project source code.
IGNORED_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        "build",
        "dist",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        "site-packages",
    }
)


def is_ignored_dir(name: str) -> bool:
    """Return True if a folder with this name should be skipped."""
    return name in IGNORED_DIRS or name.endswith(".egg-info")


def scan_python_files(repo_root: Path) -> list[str]:
    """Return the sorted repo-relative POSIX paths of all .py files under repo_root."""
    found: list[str] = []
    _walk(repo_root, repo_root, found)
    return sorted(found)


def _walk(repo_root: Path, folder: Path, found: list[str]) -> None:
    for entry in folder.iterdir():
        if entry.is_symlink():
            continue  # never follow links, for files or folders
        if entry.is_dir():
            if not is_ignored_dir(entry.name):
                _walk(repo_root, entry, found)
        elif entry.is_file() and entry.suffix == ".py":
            found.append(entry.relative_to(repo_root).as_posix())
