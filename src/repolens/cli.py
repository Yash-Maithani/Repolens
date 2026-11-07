"""Command-line interface: `repolens scan <path> [-o FILE] [--exclude PATTERN]...` (SPEC.md section 4).

Exit codes: 0 success (even if some files had errors), 2 bad path, bad
arguments, or an output file that cannot be written.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from repolens.output import to_json
from repolens.python.analyzer import analyze

EXIT_OK = 0
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repolens",
        description="Local-first static architecture analysis for Python projects.",
    )
    commands = parser.add_subparsers(dest="command")
    scan = commands.add_parser("scan", help="scan a project and write its import graph as JSON")
    scan.add_argument("path", help="folder of the project to scan")
    scan.add_argument("-o", "--output", metavar="FILE", help="write JSON to FILE instead of stdout")
    scan.add_argument(
        "--exclude",
        metavar="PATTERN",
        action="append",  # repeatable: each --exclude adds one pattern to a list
        default=[],
        help=(
            "skip .py files whose repo-relative path (with / separators) matches "
            "PATTERN (fnmatch rules; '*' also matches '/'). Repeatable. "
            "Example: --exclude 'tests/fixtures/*'"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)  # bad arguments: argparse exits with code 2
    if args.command is None:
        parser.print_usage(sys.stderr)
        return EXIT_USAGE

    repo_root = Path(args.path)
    if not repo_root.is_dir():
        print(f"repolens: error: not a folder: {args.path}", file=sys.stderr)
        return EXIT_USAGE

    # Fail fast (D36): check the output location BEFORE the scan, so a typo
    # in -o does not cost a full scan. The write below can still fail (for
    # example no permission), and that is also exit 2.
    if args.output:
        output = Path(args.output)
        if not output.parent.is_dir():
            print(
                f"repolens: error: cannot write {args.output}: folder does not exist",
                file=sys.stderr,
            )
            return EXIT_USAGE
        if output.is_dir():
            print(f"repolens: error: cannot write {args.output}: it is a folder", file=sys.stderr)
            return EXIT_USAGE

    # Encode to UTF-8 bytes ourselves. Writing text would let Windows turn
    # "\n" into "\r\n" and use a non-UTF-8 console encoding, so the output
    # would differ between machines.
    data = to_json(analyze(repo_root, exclude=args.exclude)).encode("utf-8")

    if args.output:
        try:
            Path(args.output).write_bytes(data)
        except OSError as exc:
            reason = exc.strerror or type(exc).__name__
            print(f"repolens: error: cannot write {args.output}: {reason}", file=sys.stderr)
            return EXIT_USAGE
    else:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
