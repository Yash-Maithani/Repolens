# RepoLens

RepoLens is a command-line tool that reads the source code of a Python or Java project on your own machine and shows how its modules depend on each other. The goal is to help you keep your intended layers (for example controller -> service -> repository) and avoid import cycles, without writing custom architecture tests and without uploading your code anywhere.

## Status

Early development, Phase 1. Not usable yet.

## Planned usage

```bash
repolens scan path/to/project -o graph.json
```

This will write a JSON file that lists the project's modules and the imports between them.

## What RepoLens will not do

- No AI.
- No runtime analysis. RepoLens does not run your code.
- Static imports only. Dynamic imports such as `importlib.import_module(...)` are recorded separately and are never treated like normal imports.
- No cloud service and no account. Everything runs locally.

## License

MIT. See [LICENSE](LICENSE).
