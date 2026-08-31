# MACHINE HISTORY — release-significant milestones

Purpose: compact provenance only. Stable behavior belongs in `CONTEXT.md` / `CAPABILITIES.md`; current engineering truth belongs in `STATE.md`. Human docs must not reproduce this PR history.

## Merged milestones

| PR | Merge SHA / CI | Result |
|---|---|---|
| #17 | `83a27d9350a6018abc272e9afebdef5d660de519` | durable target-operation journal / control-plane v4 |
| #19 | `fd6d5039a5852e32d823b178970816ff292472a2` | provider-native downstream recovery |
| #21 | `6377eafd4875c3cfe1d7bf21a982f6c11d47aea1` | production control-plane backend certification contract |
| #22 | `650b7d30b2e31e21d01c56465e8871b91aae4779` | Fabric REST Job Scheduler + Data Pipeline backend |
| #24 | `2fa8e2c4bc6875b529a4968694722d4108a635ff` | SQLAlchemy relational runtime repository |
| #26 | `8f23942acd5b03e1d7bf21a982f6c11d47aea1` | Copy Job + Spark Job Definition REST transports |
| #28 | `67562e4312dc9c37e8b7fb8d79535bb621bd573f` | Fabric Warehouse same-transaction target commit proof |
| #30 | `732920e214ccdead20c632f7e70c0eb8f1267f0d`, Actions `33250676068` | approved DEV integration evidence harness |
| #32 | `e42dee86db3d4102c7264bc0d1f01f83fb8aade2`, Actions `33251177339`, 407 | approved-run preflight + read-only item smoke |
| #34 | `1c7d67bedd125f5fb5e983be791085fd1eaa9b0e`, Actions `33253215030`, 419 | orthogonal capture semantics + exact 14 presets |
| #35 | `bf215fcb3538f9806b4002d2f154dbd46ae19412`, Actions `33253394201`, 430 | semantic onboarding + CLI |
| #37 | `d69b2ff49f984331b6753bcd9274ea9a298ce798`, Actions `33253581049`, 441 | full-baseline to WATERMARK bootstrap |
| #39 | `014cd334105de6f867b6320509b94147a444a2fa`, Actions `33253817758`, 455 | strict staged evidence merge |
| #41 | `ad856d864eb5dec35f3c97ec66ca9e920cfa5e28`, Actions `33254804867`, 466 | approved production control-plane certification runner |
| #43 | `395736a3a400480da5876a43591961c478426314`, Actions `33255472348`, 477 | approved Fabric Pipeline evidence runner |
| #45 | `f8c2f24264480613ca048aaece09371a72aa529a`, Actions `33279105627`, 490 | approved Copy Job + Spark capture evidence runner |
| #47 | Actions `33279727906`, 501 | approved Fabric Warehouse commit/recovery runner |
| #49 | Actions `33282725576`, 513 | approved Warehouse ambiguous-COMMIT fault-drill runner |
| #51 | `4dfa5e22fd8eab67406ced8af954f2d81ad18321`, Actions `33283668067`, 525 | exact-session termination absence-certifier contract |
| #53 | `b9187d93015d921614147831da1336b2d91f3e22`, Actions `33284190041`, 534 | approved session-termination recovery with separate Admin authorization |
| #55 | `46c10ab00fefc2ca546fd7f2bea369a7037216da`, Actions `33285255666`, 534 | split stable human docs from exact machine docs |
| #57 | `3ddbb873029a13985af4e563228629c1efc4f7d4`, Actions `33286548611`, 539 | extracted removable CLI leaf package |
| #59 | `c5471b7a417525e3a73d309b786f331192b22c0f`, Actions `33287715582`, 561 | grouped evidence + approved exact-run implementation under `evidence/` |
| #61 | `83cc031d542723e42f064259aacff6c11ca8b015`, Actions `33288491628`, 562 | removed root evidence aliases and `cli_router.py` |
| #63 | `661651387fd75ad548da8b049da59529b296ec9a`, Actions `33288912694`, 575 | canonical `control_plane/`; removed flat control-plane/repository/operator/journal modules |
| #65 | `49ce1bf8d6753434ae8f2975b635183a1ace5251`, Actions `33290270657`, 577 | moved retained evidence safety to `evidence/safety.py` |
| #66 | `7671c2a0e65537ca7746fa2c4601e1457fcb033d`, Actions `33290435230`, 582 | canonical `deployment/`; root deployment/delivery removed |
| #67 | `b0a74fc234ade150e3e9786a176b8d5beae78bf8`, Actions `33290795177`, 589 | canonical semantic `contracts/`; removed mixed root contract modules and facade |
| #68 | `a117c27a32b4e4f9c4bf1a7dcf6a35e9d3f6d16b`, Actions `33291942505`, 592 | root package made namespace-only |
| #70 | `3811fed18c9b1fdfac8f9dfcdb0125a62e1c1836`, Actions `33292200455`, 598 | moved watermark/SCD2/Bronze/reconciliation/Fabric auth to explicit domain owners |
| #71 | `e3d3fd2a67c8a86b6bedb7b127ba53915599e8d8`, Actions `33292421348`, 605 | moved final root implementation modules; source root contains only namespace `__init__.py` |
| #72 | `80d0efec39899d01b1a61515396896c397a3b70a`, Actions `33292517022`, 608 | removed recovery package re-export facade |
| #73 | `7c55c8179e50386d83ca945665e41251826eaf81`, Actions `33292620504`, 612 | removed capture and apply package re-export facades |
| #74 | `0b82a55981700484e68c5fb9f68de7c94a68b75b`, Actions `33302223695`, 615 | removed quality and orchestration package re-export facades |
| #76 | `1c3669cad03b2209527d7f0727fd879c45dda4df` | non-destructive customer/domain `project-init` scaffold contract |
| #78 | `8094e4742507c23ffad16220aebd6862876a3cd0`, Actions `33305885406`, 627 | whole-project fail-closed `project-validate` dry-run contract |
| #80 | `353b43c37077a1ffc9e22b6c76ae5494a164306e`, PR Actions `33309737895`, main Actions `33309805619`, 636 | 0.4 exact-candidate fail-closed release-readiness aggregation; ordinary readiness intentionally BLOCKED |
| #82 | `7f7849b9319df43ef382574747bfe27ee6378403`, PR Actions `33310317289`, main Actions `33310363412`, 644 | exact candidate wheel identity + exact certified-byte release promotion; no release-time rebuild |
| #84 | `bb9b7ed74e2696978c546011c893fb316ffdd57c`, final PR Actions `33314924064`, main Actions `33314977393`, 653 | exact-candidate certification aggregation, integration evidence template, credential-safe release proof retention, manual certification workflow |
| #86 | `0f70e037806482c677fccae0ce9432504f2a9885`, PR Actions `33342779028`, main Actions `33342806854`, 664 | strict exact-candidate partial `ReleaseReadinessProofBundle` merge; contradictory substantive proof has no precedence |
| #87 | `5a2edffe5930e9b8a2a79f66f4580ca4d9df2b4e`, PR Actions `33343182775`, main Actions `33343223496`, 670 | exact-candidate non-integration release-proof producer; direct PASS limited to source/wheel/customer observations and live business-path proof remains external |
| #88 | `1632aefe8c1fd71098200c434a1648d0385f4967`, PR Actions `33346419772`, main Actions `33346470401`, 717 | representative five-gate business-path evidence contract/producer, explicit Pipeline rerun, canonical plan-path guard and distinct framework-wheel/domain-release identities |
| #90 | `7e12a320e73aa06f3e80f57e3deed14a6cc7add0`, final PR Actions `33349005817`, main Actions `33349064335`, 728 | exact-candidate integration-evidence producer, customer-owned representative Pipeline dataset binding, staged approved-runner orchestration and strict certified merge; no live Fabric proof claimed |
| #92 | `d5eed17f2ec2f869b4e3a448597e6d8d600568ea`, final PR Actions `33356959856`, main Actions `33357032461`, 734 | exact customer/domain `domain_release_hash` bound through business-path proof, strict release-proof merge, candidate certification report and pre-tag exact-byte promotion checks |
| #94 | `abc8b3a2b80b3f6babf88fdc2347a3bfe69be356`, final PR Actions `33357795244`, main Actions `33357846835`, 738 | removed obsolete runner-level unbound business-path proof bundle/writer; candidate proof packaging now exclusively requires exact customer `ReleaseManifest` |

## Integrated design decisions

```text
three-repository ownership
capture semantics separate from apply semantics
control plane stores runtime/deployment state, not complete DatasetConfig truth
metadata-driven orchestration and failure isolation
semantic model separate from physical execution engine
framework-first semantics with bounded provider-native delegation
CLI is a removable leaf
evidence/ owns integration evidence, approved exact-run runners, release readiness and candidate certification
control_plane/ owns relational state
deployment/ owns release/delivery and candidate artifact identity
contracts/ owns provider-neutral semantic/runtime contracts
source root and major package roots are namespace-only
callers import explicit owner submodules
unreleased 0.4.0 does not preserve obsolete aliases
removed paths and broad facades are contract-tested as absent
one business/domain repo may contain mixed FULL/WATERMARK/CDC and SCD1/SCD2; execution_group handles operational grouping
release readiness binds exact candidate source SHA and exact artifact SHA for live evidence
integration-backed release gates cannot be bypassed by generic/manual PASS proof
main candidate artifact binds source SHA + CI run/attempt + wheel filename/version + inner SHA256
candidate certification validates retained proof; it does not execute Fabric or manufacture evidence
candidate certification accepts only exact-candidate successful explicit producer runs from fixed workflow paths
release proof references/details are screened for obvious credential material before certified retention
release workflow promotes already-certified bytes and must never rebuild the wheel
candidate artifact existence does not mean candidate has been selected/frozen
certification workflow existence does not mean live certification has happened
framework wheel SHA256 and customer/domain release hash are independent exact identities
business-path proof packaging binds evaluator output to the exact customer ReleaseManifest rather than accepting domain identity from workflow input
approved business-path runner returns evaluated execution evidence only and does not package candidate release proof
business_path_release_proof.py is the sole business-path candidate proof packaging owner and requires exact customer ReleaseManifest
strict candidate release-proof merge requires the same non-empty domain_release_hash on all partial bundles
candidate certification requires release proof and integration evidence to carry the same domain_release_hash
release promotion re-checks readiness report, release proof and integration domain_release_hash equality before tag creation
representative business-path PASS belongs only to the framework evaluator over driver/observer/provider/durable-outcome facts
explicit Pipeline rerun starts from separately retained fully certified integration evidence and never mutates it
cleanup failure blocks business-path proof publication
candidate integration producer may orchestrate approved runners and validate already-produced PASS, but may never synthesize integration PASS
representative Pipeline dataset selection remains customer/domain-owned and is carried by the physical binding, not chosen by the framework workflow
0.4 is feature-frozen and remains unreleased until required readiness blockers reach zero
Debezium/Kafka is optional in the 0.4 certification matrix unless explicitly promoted into GA scope
```

## Historical evidence discipline

```text
provider REST implementation != live provider proof
CI commit-then-raise double != real network/driver fault proof
simulated framework ACK loss != real COMMIT disconnect
session-termination provider contract != production-approved Admin/KILL proof
project-validate PASS != live Fabric readiness
release-readiness contract PASS != release readiness
GitHub Actions artifact archive digest != exact inner wheel SHA256
source/version equality != permission to reuse evidence across rebuilt artifacts
candidate-capable main artifact != frozen/certified candidate
candidate-certification contract != retained live certification
business-path producer contract != retained live business-path proof
business-path execution report != domain-bound candidate proof bundle
integration producer contract != retained live integration proof
customer input producer contract != selected-candidate input artifact
exact domain identity contract != live customer/domain evidence
exact-byte promotion contract != live certification
```
