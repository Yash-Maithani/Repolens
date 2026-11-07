"""The frozen stdlib list (SPEC.md section 6, decision D8).

CI runs this on Python 3.10, 3.11, 3.12 and 3.13. If a Python version adds a
stdlib module that is missing from the frozen list, this test fails there.
"""

from __future__ import annotations

import sys

from repolens.python.stdlib_names import STDLIB_NAMES


def test_running_python_stdlib_is_a_subset_of_the_frozen_list() -> None:
    missing = set(sys.stdlib_module_names) - STDLIB_NAMES
    assert missing == set(), f"add these to stdlib_names.py: {sorted(missing)}"


def test_removed_modules_still_count_as_stdlib() -> None:
    # distutils, imp and asyncore were removed in 3.12; cgi and telnetlib in 3.13.
    for name in ["distutils", "imp", "asyncore", "cgi", "telnetlib", "lib2to3"]:
        assert name in STDLIB_NAMES


def test_newer_modules_count_as_stdlib() -> None:
    assert "tomllib" in STDLIB_NAMES  # added in 3.11


def test_common_third_party_names_are_not_stdlib() -> None:
    for name in ["requests", "numpy", "pytest", "setuptools", "pip"]:
        assert name not in STDLIB_NAMES
