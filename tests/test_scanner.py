"""Scanner: ignored folders are skipped; paths are POSIX, relative and sorted."""

from __future__ import annotations

from pathlib import Path

from repolens.scanner import IGNORED_DIRS, scan_python_files


def _touch(root: Path, relative: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def test_ignored_folders_are_skipped(tmp_path: Path) -> None:
    # Built in a temporary folder because .gitignore would keep folders such
    # as .venv and build out of a committed fixture.
    _touch(tmp_path, "keep.py")
    for name in sorted(IGNORED_DIRS) + ["mypkg.egg-info"]:
        _touch(tmp_path, f"{name}/hidden.py")
        _touch(tmp_path, f"pkg/{name}/nested_hidden.py")  # ignored at any depth
    _touch(tmp_path, "pkg/keep_too.py")

    assert scan_python_files(tmp_path) == ["keep.py", "pkg/keep_too.py"]


def test_only_py_files_are_returned(tmp_path: Path) -> None:
    _touch(tmp_path, "a.py")
    _touch(tmp_path, "notes.txt")
    _touch(tmp_path, "b.pyc")
    _touch(tmp_path, "c.pyi")

    assert scan_python_files(tmp_path) == ["a.py"]


def test_paths_are_posix_and_relative(tmp_path: Path) -> None:
    _touch(tmp_path, "pkg/sub/mod.py")

    paths = scan_python_files(tmp_path)

    assert paths == ["pkg/sub/mod.py"]
    for path in paths:
        assert "\\" not in path
        assert not Path(path).is_absolute()
        assert str(tmp_path) not in path


def test_paths_are_sorted(tmp_path: Path) -> None:
    for relative in ["z.py", "b/a.py", "a.py", "b/__init__.py", "a/z.py"]:
        _touch(tmp_path, relative)

    paths = scan_python_files(tmp_path)

    assert paths == ["a.py", "a/z.py", "b/__init__.py", "b/a.py", "z.py"]
    assert paths == sorted(paths)
