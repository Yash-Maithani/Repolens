"""Shared test helpers."""

from __future__ import annotations

from pathlib import Path

from repolens.model import ImportClass, Module

FIXTURES = Path(__file__).parent / "fixtures"


def fake_resolve(
    importer: Module, module: str | None, names: list[str], level: int, known_modules: set[str]
) -> list[tuple[str, ImportClass]]:
    """A stand-in resolver for tests that must not depend on the owner's resolve().

    It does no real resolution: the target is the import as written
    ("..core" for `from ..core import y`) and every edge is EXTERNAL.
    """
    return [("." * level + (module or ""), ImportClass.EXTERNAL)]
