# Control-plane package

This folder is the only implementation owner for relational control-plane behavior.

```text
schema.py                    SQLAlchemy tables + explicit schema migration contract
io.py                        capture/reprocess/quarantine/CDC runtime persistence helpers
schema_evidence.py           immutable schema-change observation persistence
certification.py             production backend profile + conformance certification
repository.py                repository protocol + deterministic in-memory adapter
sqlalchemy_repository.py     production-oriented SQLAlchemy repository
operator.py                  typed read-only operational views
target_operation_journal.py  durable target-operation CAS/event journal persistence
```

The package root intentionally does not re-export the old flat `control_plane.py` API.
Use explicit submodule imports so ownership remains visible in source code.

`target_operations.py` remains outside this folder because it defines provider-neutral
semantic operation identity/state; only its relational journal persistence lives here.
