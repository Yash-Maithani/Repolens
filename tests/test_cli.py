"""CLI: exit codes and where the output goes (SPEC.md section 4).

The owner's resolve() is replaced with helpers.fake_resolve, so these tests
check only the command-line behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from helpers import FIXTURES, fake_resolve
from repolens import cli
from repolens.python import resolver

PROJECT = FIXTURES / "flat_project"


@pytest.fixture(autouse=True)
def _use_fake_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resolver, "resolve", fake_resolve)


def test_scan_to_stdout_exits_0(capsysbinary: pytest.CaptureFixture[bytes]) -> None:
    assert cli.main(["scan", str(PROJECT)]) == 0
    out = capsysbinary.readouterr().out
    assert out.startswith(b"{\n")
    assert out.endswith(b"}\n")
    assert b"\r\n" not in out


def test_scan_to_file_matches_stdout(
    tmp_path: Path, capsysbinary: pytest.CaptureFixture[bytes]
) -> None:
    target = tmp_path / "graph.json"
    assert cli.main(["scan", str(PROJECT), "-o", str(target)]) == 0
    assert cli.main(["scan", str(PROJECT)]) == 0
    assert target.read_bytes() == capsysbinary.readouterr().out


def test_missing_path_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["scan", str(tmp_path / "does-not-exist")]) == 2
    assert "not a folder" in capsys.readouterr().err


def test_file_instead_of_folder_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["scan", str(PROJECT / "app" / "repo.py")]) == 2


def test_unwritable_output_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "missing-folder" / "graph.json"
    assert cli.main(["scan", str(PROJECT), "-o", str(target)]) == 2
    assert "cannot write" in capsys.readouterr().err


def test_no_command_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([]) == 2


def test_bad_arguments_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["scan"])  # missing <path>
    assert excinfo.value.code == 2

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["scan", str(PROJECT), "--unknown"])
    assert excinfo.value.code == 2
