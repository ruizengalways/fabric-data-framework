# Contributing

Use this repository for reusable framework behavior, not project-specific business configuration.

Before changing code:

1. Read [`docs/CODE_READING_GUIDE.md`](docs/CODE_READING_GUIDE.md) to understand the current runtime and ownership.
2. Read [`docs/DEVELOPMENT_GUIDE.md`](docs/DEVELOPMENT_GUIDE.md) for safe secondary-development rules, change-impact mapping, testing, debugging, and review expectations.
3. Check [`docs/internal/IMPLEMENTATION_MAP.md`](docs/internal/IMPLEMENTATION_MAP.md) for the canonical owner module.

## Workflow

```text
current main
-> focused feature/docs branch
-> code + tests + canonical docs in the same change
-> pull request
-> exact PR-head CI green
-> merge using the expected head SHA
-> verify post-merge main CI
```

Do not develop framework features directly on `main`.

## Required engineering rules

- keep capture semantics separate from apply semantics and provider mechanics;
- keep one canonical owner for each semantic concept;
- fail closed when required evidence or target outcome is missing/ambiguous;
- do not treat provider `Completed` as framework semantic success;
- do not add project/customer-specific logic to the reusable framework;
- do not introduce compatibility shims, deprecated aliases, duplicate old paths, or silent fallbacks by default;
- update focused tests and the owning canonical document with behavior changes;
- never upgrade source/local/package proof into a real Fabric PASS claim;
- assess whether the change alters wheel bytes and therefore invalidates a previously selected executable candidate for release purposes.

Local development gate:

```bash
python -m pip install -e '.[dev]'
pytest -q
ruff check src tests
```

See [`docs/TESTING_AND_CERTIFICATION.md`](docs/TESTING_AND_CERTIFICATION.md) for package and Fabric proof gates, and [`docs/RELEASE.md`](docs/RELEASE.md) for candidate/release rules.
