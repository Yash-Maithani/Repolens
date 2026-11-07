# RepoLens

RepoLens is a command-line tool that reads the source code of a Python or Java project on your own machine and shows how its modules depend on each other. The goal is to help you keep your intended layers (for example controller -> service -> repository) and avoid import cycles, without writing custom architecture tests and without uploading your code anywhere.

## Status

Early development. Phases 1 and 2 work: scan Python projects to JSON and report import cycles. Not stable yet.

## Usage

RepoLens is not on PyPI yet. Install it from a clone of this repository (Python 3.10 or newer):

```bash
pip install -e .
```

Scan the project in the current folder and write the result to `graph.json`:

```bash
repolens scan . -o graph.json
```

Use `--exclude` (repeatable) to skip files, for example sample projects inside your tests. Patterns are matched against the path with `/` separators, and `*` also matches `/`:

```bash
repolens scan . -o graph.json --exclude "tests/fixtures/*"
```

The JSON lists the modules, every import with the file and line it came from (`edges`), and the import cycles. This is a real excerpt from scanning a small project where `app.a` imports `app.b`, `app.b` imports `app.c`, and `app.c` imports `app.a`:

```text
{
  "cycles": [
    {
      "edges": [
        {
          "classification": "local",
          "evidence": {
            "file": "app/a.py",
            "line": 1,
            "text": "from app import b"
          },
          "kind": "import",
          "source": "app.a",
          "target": "app.b"
        },
        ... (app.b -> app.c and app.c -> app.a)
      ],
      "modules": [
        "app.a",
        "app.b",
        "app.c"
      ]
    }
  ],
  "edges": [ ... ],
  ...
  "schema_version": 2
}
```

Each import is classified as `local`, `stdlib`, `external` or `unresolved`. Only local imports can form a cycle.

## What RepoLens will not do

- No AI.
- No runtime analysis. RepoLens does not run your code.
- Static imports only. Dynamic imports such as `importlib.import_module(...)` are recorded separately and are never treated like normal imports.
- No cloud service and no account. Everything runs locally.

## Known limitations

- For a file with a syntax error, the reported line number can differ between Python versions, because newer versions of Python report some syntax errors on a different line.
- Test helper imports that rely on pytest's `sys.path` (for example `from helpers import x` inside `tests/`) show as `external`, because RepoLens only sees the source roots, not the paths pytest adds at run time.
- Only Python is supported so far. Java is planned for Phase 3.

## License

MIT. See [LICENSE](LICENSE).
