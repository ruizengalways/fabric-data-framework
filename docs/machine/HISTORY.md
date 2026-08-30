# MACHINE HISTORY — release-significant milestones

Purpose: compact provenance only. Stable behavior belongs in `CONTEXT.md` / `CAPABILITIES.md`, not here.

## Merged milestones

| PR | Merge SHA / CI | Result |
|---|---|---|
| #17 | `83a27d9350a6018abc272e9afebdef5d660de519` | durable target-operation journal / control-plane v4 |
| #19 | `fd6d5039a5852e32d823b178970816ff292472a2` | provider-native downstream recovery |
| #21 | `6377eafd4875c3cfe1d7bf21a982f6c11d47aea1` | production control-plane backend certification contract |
| #22 | `650b7d30b2e31e21d01c56465e8871b91aae4779` | Fabric REST Job Scheduler + Data Pipeline backend |
| #24 | `2fa8e2c4bc6875b529a4968694722d4108a635ff` | SQLAlchemy relational runtime repository |
| #26 | `8f23942acd5b03d817e42b97d9f490acc6bee89f` | Copy Job + Spark Job Definition REST transports |
| #28 | `67562e4312dc9c37e8b7fb8d79535bb621bd573f` | Fabric Warehouse same-transaction target commit proof |
| #30 | `732920e214ccdead20c632f07e70c0eb8f1267f0d`, Actions `33250676068` | approved DEV integration evidence harness |
| #32 | `e42dee86db3d4102c7264bc0d1f01f83fb8aade2`, Actions `33251177339`, 407 tests | approved-run preflight + read-only item smoke |
| #34 | `1c7d67bedd125f5fb5e983be791085fd1eaa9b0e`, Actions `33253215030`, 419 | orthogonal cheatsheet semantics + exact 14 presets |
| #35 | `bf215fcb3538f9806b4002d2f154dbd46ae19412`, Actions `33253394201`, 430 | semantic onboarding + CLI |
| #37 | `d69b2ff49f984331b6753bcd9274ea9a298ce798`, Actions `33253581049`, 441 | full-baseline -> WATERMARK bootstrap |
| #39 | `014cd334105de6f867b6320509b94147a444a2fa`, Actions `33253817758`, 455 | strict staged evidence merge |
| #41 | `ad856d864eb5dec35f3c97ec66ca9e920cfa5e28`, Actions `33254804867`, 466 | approved production control-plane certification runner |
| #43 | `395736a3a400480da5876a43591961c478426314`, Actions `33255472348`, 477 | approved Fabric Pipeline evidence runner |
| #45 | `f8c2f24264480613ca048aaece09371a72aa529a`, Actions `33279105627`, 490 | approved Copy Job + Spark capture evidence runner |
| #47 | merged after Actions `33279727906`, 501 | approved Fabric Warehouse commit/recovery runner |
| #49 | code baseline before session work, Actions `33282725576`, 513 | approved Warehouse ambiguous-COMMIT fault-drill runner |
| #51 | `4dfa5e22fd8eab67406ced8af954f2d81ad18321`, Actions `33283668067`, 525 | Fabric Warehouse exact-session termination absence-certifier contract |
| #52 | docs checkpoint, Actions `33283847867`, 525 | canonicalized PR #51 state |
| #53 | `b9187d93015d921614147831da1336b2d91f3e22`, Actions `33284190041`, 534 | approved session-termination recovery wiring with separate Admin authorization |
| #54 | `c5baff6318b5facc366fa9466d23041291835fd5`, Actions `33284381347`, 534 | canonical docs checkpoint after PR #53 |
| #55 | `46c10ab00fefc2ca546fd7f2bea369a7037216da`, Actions `33285255666`, 534 | split stable human docs from exact machine/recovery docs; removed superseded flat docs/ADRs/runbooks and unified examples under root `examples/` |
| #57 | `3ddbb873029a13985af4e563228629c1efc4f7d4`, Actions `33286548611`, 539 | extracted CLI into removable leaf package; console entrypoint moved to `fabric_data_framework.cli`; added source-code map and CLI-isolation contracts |
| #59 | `c5471b7a417525e3a73d309b786f331192b22c0f`, Actions `33287715582`, 561 | grouped integration evidence and approved exact-run implementations under canonical `evidence/`; historical root modules became same-module compatibility aliases |

## Important historical design decisions now integrated into current model

These should not be re-expanded into human changelog/runbooks unless behavior changes:

```text
three-repository ownership
capture semantics separate from apply semantics
control plane stores runtime/deployment state, not complete DatasetConfig truth
metadata-driven orchestration and failure isolation
immutable release artifact + delivery CLI
Pipeline/Spark execution boundary
semantic model separate from physical execution engine
framework-first semantics with bounded provider-native stage delegation
CLI is a leaf presentation layer; reusable core must not depend on it
evidence/ is the canonical implementation owner for integration evidence and approved exact-run executors
historical root evidence/approved module paths are compatibility aliases only
```

Current versions of those decisions are summarized in human `CONCEPTS.md` / `REPOSITORY_GUIDE.md` and machine `CONTEXT.md` / `IMPLEMENTATION_MAP.md`.

## Historical evidence discipline

Several implementation stages were intentionally split to avoid overclaim:

```text
provider REST implementation != live provider proof
CI commit-then-raise double != real network/driver fault proof
simulated framework ACK loss != real COMMIT disconnect
session-termination provider contract != production-approved Admin/KILL proof
CLI/evidence readability refactors != new provider or production evidence
```

Keep these distinctions even if future implementation refactors merge code paths.
