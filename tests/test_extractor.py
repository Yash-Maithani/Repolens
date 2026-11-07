"""Extractor: every import form, dynamic imports, observations and bad files.

These tests only check what the extractor READS. They do not need resolve().
The fixture is tests/fixtures/imports_project/app/auth/service.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from helpers import FIXTURES
from repolens.model import EdgeKind
from repolens.python.extractor import (
    REASON_NON_LITERAL,
    REASON_RELATIVE,
    ExtractResult,
    RawImport,
    extract_file,
)

PROJECT = FIXTURES / "imports_project"
SERVICE = "app/auth/service.py"


@pytest.fixture(scope="module")
def service() -> ExtractResult:
    return extract_file(PROJECT, SERVICE)


def _find(result: ExtractResult, line: int) -> list[RawImport]:
    return [raw for raw in result.imports if raw.evidence.line == line]


def _shape(raw: RawImport) -> tuple:
    return (raw.module, raw.names, raw.level, raw.kind)


def test_file_parses_without_error(service: ExtractResult) -> None:
    assert service.error is None


def test_absolute_import(service: ExtractResult) -> None:
    assert [_shape(r) for r in _find(service, 2)] == [("os", (), 0, EdgeKind.IMPORT)]
    assert [_shape(r) for r in _find(service, 3)] == [("app.core.db", (), 0, EdgeKind.IMPORT)]


def test_from_import(service: ExtractResult) -> None:
    assert [_shape(r) for r in _find(service, 4)] == [("app", ("core",), 0, EdgeKind.IMPORT)]


def test_relative_import_level_1(service: ExtractResult) -> None:
    assert [_shape(r) for r in _find(service, 5)] == [(None, ("helpers",), 1, EdgeKind.IMPORT)]


def test_relative_import_level_2(service: ExtractResult) -> None:
    # "as database" is an alias; the imported name is still "db".
    assert [_shape(r) for r in _find(service, 6)] == [("core", ("db",), 2, EdgeKind.IMPORT)]


def test_import_inside_try_except(service: ExtractResult) -> None:
    assert [_shape(r) for r in _find(service, 10)] == [("json", (), 0, EdgeKind.IMPORT)]


def test_function_level_import(service: ExtractResult) -> None:
    assert [_shape(r) for r in _find(service, 16)] == [("csv", (), 0, EdgeKind.IMPORT)]


def test_type_checking_import_is_recorded_normally(service: ExtractResult) -> None:
    assert [_shape(r) for r in _find(service, 35)] == [("decimal", (), 0, EdgeKind.IMPORT)]


def test_literal_importlib_is_dynamic(service: ExtractResult) -> None:
    [raw] = _find(service, 21)
    assert _shape(raw) == ("app.plugins.alpha", (), 0, EdgeKind.DYNAMIC)
    assert raw.evidence.text == 'importlib.import_module("app.plugins.alpha")'


def test_literal_dunder_import_is_dynamic(service: ExtractResult) -> None:
    assert [_shape(r) for r in _find(service, 24)] == [
        ("app.plugins.gamma", (), 0, EdgeKind.DYNAMIC)
    ]


def test_non_literal_importlib_is_an_observation(service: ExtractResult) -> None:
    assert _find(service, 22) == []  # no import, so no edge later
    [observation] = [o for o in service.observations if o.line == 22]
    assert observation.file == SERVICE
    assert observation.reason == REASON_NON_LITERAL
    assert observation.text == "importlib.import_module(name)"


def test_relative_dynamic_import_is_an_observation(service: ExtractResult) -> None:
    assert _find(service, 23) == []
    [observation] = [o for o in service.observations if o.line == 23]
    assert observation.reason == REASON_RELATIVE


def test_multi_line_import_evidence(service: ExtractResult) -> None:
    [raw] = _find(service, 27)
    assert _shape(raw) == ("app.core", ("db", "helpers_x"), 0, EdgeKind.IMPORT)
    assert raw.evidence.file == SERVICE
    assert raw.evidence.text == "from app.core import ( db, helpers_x, )"


def test_evidence_text_is_the_stripped_statement(service: ExtractResult) -> None:
    [raw] = _find(service, 16)  # indented inside a function
    assert raw.evidence.text == "import csv"


def test_syntax_error_goes_to_errors() -> None:
    result = extract_file(PROJECT, "app/broken.py")
    assert result.imports == []
    assert result.error is not None
    assert result.error.file == "app/broken.py"
    assert result.error.line == 2
    assert result.error.type == "SyntaxError"


def test_decode_error_goes_to_errors(tmp_path: Path) -> None:
    # The bad byte is on line 3, after the lines Python checks for an
    # encoding declaration, so it fails while reading, not while detecting.
    (tmp_path / "bad.py").write_bytes(b"x = 1\ny = 2\nz = '\xff'\n")
    result = extract_file(tmp_path, "bad.py")
    assert result.error is not None
    assert (result.error.file, result.error.line, result.error.type) == (
        "bad.py",
        None,
        "UnicodeDecodeError",
    )
