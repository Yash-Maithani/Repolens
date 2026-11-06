"""Find every import in one Python file (SPEC.md section 7).

The extractor only READS imports. It does not decide what they point to:
that is the resolver's job. Keeping the two steps apart means each one can be
tested on its own.

What is found:
- every `import x` and `from x import y`, including relative imports, imports
  inside functions, inside try/except, and inside `if TYPE_CHECKING:`
  (ast.walk visits every node in the tree, wherever it is);
- literal `importlib.import_module("x")` and `__import__("x")`, as dynamic
  imports;
- dynamic imports that cannot be read statically, as Observations.

A file that cannot be read or parsed becomes a FileError. The extractor never
raises for a bad file, so one broken file never stops a scan.
"""

from __future__ import annotations

import ast
import tokenize
from dataclasses import dataclass, field
from pathlib import Path

from repolens.model import EdgeKind, Evidence, FileError, Observation

REASON_NON_LITERAL = "non-literal dynamic import"
REASON_RELATIVE = "relative dynamic import"


@dataclass(frozen=True)
class RawImport:
    """One import as written in the source, before resolution.

    These four fields are exactly what resolve() receives:
    - `import a.b`            -> module="a.b", names=(), level=0
    - `from a import b, c`    -> module="a", names=("b", "c"), level=0
    - `from ..core import y`  -> module="core", names=("y",), level=2
    - `from . import x`       -> module=None, names=("x",), level=1
    - `importlib.import_module("a.b")` -> module="a.b", names=(), level=0,
      kind=DYNAMIC
    """

    module: str | None
    names: tuple[str, ...]
    level: int
    kind: EdgeKind
    evidence: Evidence


@dataclass
class ExtractResult:
    imports: list[RawImport] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    error: FileError | None = None


def extract_file(repo_root: Path, rel_path: str) -> ExtractResult:
    """Read and analyse one file. rel_path is repo-relative POSIX."""
    try:
        # tokenize.open reads the encoding declaration (PEP 263) the same way
        # Python does, then decodes the file with it.
        with tokenize.open(repo_root / rel_path) as handle:
            source = handle.read()
    except SyntaxError as exc:  # invalid or missing encoding declaration
        return ExtractResult(error=FileError(rel_path, exc.lineno, type(exc).__name__))
    except UnicodeDecodeError:
        return ExtractResult(error=FileError(rel_path, None, "UnicodeDecodeError"))
    except OSError:
        return ExtractResult(error=FileError(rel_path, None, "OSError"))
    return extract_source(source, rel_path)


def extract_source(source: str, rel_path: str) -> ExtractResult:
    """Analyse source text. rel_path is only used for evidence and errors."""
    if "\x00" in source:
        # Python 3.10 and 3.11 raise ValueError for null bytes, 3.12+ raise
        # SyntaxError with a line number. Report it the same way everywhere.
        return ExtractResult(error=FileError(rel_path, None, "SyntaxError"))
    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError as exc:  # also IndentationError and TabError
        return ExtractResult(error=FileError(rel_path, exc.lineno, type(exc).__name__))

    result = ExtractResult()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            evidence = _evidence(source, node, rel_path)
            for alias in node.names:
                result.imports.append(RawImport(alias.name, (), 0, EdgeKind.IMPORT, evidence))
        elif isinstance(node, ast.ImportFrom):
            evidence = _evidence(source, node, rel_path)
            names = tuple(alias.name for alias in node.names)
            result.imports.append(
                RawImport(node.module, names, node.level or 0, EdgeKind.IMPORT, evidence)
            )
        elif isinstance(node, ast.Call):
            _extract_dynamic(source, node, rel_path, result)

    # ast.walk visits nodes breadth first, not in line order. Sorting by line
    # makes the list easier to read; the sort is stable, so equal lines keep
    # their (deterministic) walk order.
    result.imports.sort(key=lambda raw: raw.evidence.line)
    return result


def _evidence(source: str, node: ast.AST, rel_path: str) -> Evidence:
    """First line of the statement, and its full text with whitespace collapsed (D12)."""
    segment = ast.get_source_segment(source, node) or ""
    return Evidence(rel_path, node.lineno, " ".join(segment.split()))


def _extract_dynamic(source: str, call: ast.Call, rel_path: str, result: ExtractResult) -> None:
    function = _dynamic_function(call)
    if function is None:
        return
    evidence = _evidence(source, call, rel_path)

    name_arg = _argument(call, 0, "name")
    if not (isinstance(name_arg, ast.Constant) and isinstance(name_arg.value, str) and name_arg.value):
        result.observations.append(
            Observation(rel_path, evidence.line, evidence.text, REASON_NON_LITERAL)
        )
        return

    if name_arg.value.startswith(".") or _has_relative_level(call, function):
        result.observations.append(
            Observation(rel_path, evidence.line, evidence.text, REASON_RELATIVE)
        )
        return

    result.imports.append(RawImport(name_arg.value, (), 0, EdgeKind.DYNAMIC, evidence))


def _dynamic_function(call: ast.Call) -> str | None:
    """Return "importlib.import_module" or "__import__" if the call is one of them."""
    func = call.func
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "import_module"
        and isinstance(func.value, ast.Name)
        and func.value.id == "importlib"
    ):
        return "importlib.import_module"
    if isinstance(func, ast.Name) and func.id == "__import__":
        return "__import__"
    return None


def _argument(call: ast.Call, position: int, keyword: str) -> ast.expr | None:
    """Return a call argument given by position or by keyword, or None."""
    if len(call.args) > position:
        return call.args[position]
    for kw in call.keywords:
        if kw.arg == keyword:
            return kw.value
    return None


def _has_relative_level(call: ast.Call, function: str) -> bool:
    """True if an __import__ call passes a level other than a literal 0."""
    if function != "__import__":
        return False
    level = _argument(call, 4, "level")
    if level is None:
        return False
    return not (isinstance(level, ast.Constant) and level.value == 0)
