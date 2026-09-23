# Architecture & product decision log (ADR-lite)

One entry per decision. Newest last. Format: date · decision · why · consequences · status.

## ADR-001 · 2026-09-17 · Native SwiftUI + Swift package instead of React Native / Expo
Why: on-device perception (AVFoundation/Vision), HealthKit, file protection and offline determinism
are native concerns; the original concept's RN/Wasm/SQLite stack was never approved.
Consequences: iOS-only for now; Android would be a second native client sharing the Python core.
Status: accepted.

## ADR-002 · 2026-09-17 · Whole-state JSON snapshot persistence with atomic writes
Why: small prototype; transactional copy→mutate→save→publish is simple and testable.
Consequences: O(history) serialization per command; must be windowed or replaced by a database
before multi-year histories. Not a production storage claim.
Status: accepted, revisit at pilot end.

## ADR-003 · 2026-09-18 · Direct OSS use limited to free-exercise-db (Unlicense) and RepCounterSDK (MIT)
Why: permissive licenses; descriptive catalog and native rep detection only. Nine other fitness
repos were researched and rejected as code sources (AGPL or architectural mismatch).
Consequences: catalog records are descriptions, never reviewed policy.
Status: accepted.

## ADR-004 · 2026-09-18 · Domain rules moved to embedded CPython 3.13 (BeeWare Python-Apple-support 3.13-b13)
Why: owner wants a Python-heavy monorepo, Linux-testable rules and a path to a future backend/ML,
while staying local-first with no HTTP boundary.
Consequences: xcframework download at setup; PEP 730 framework packaging in a build phase;
versioned JSON contract v1.0; Swift becomes a thin client. Must never run per camera frame.
Status: accepted. 2026-09-22 review: keep and lock; no further infra work until P1 gate.

## ADR-005 · 2026-09-22 · openGym (DuarteSantos8 / alexpcosta fork) rejected for code or data reuse
Why: AGPL-3.0 code; its exercise dataset (hasaneyldrm/exercises-dataset) is unlicensed.
Consequences: may be read as a design reference (progression engine shapes, LLM-coach boundary,
CSV importer field mappings) but nothing is copied. MuscleMap (MIT) may be used directly from upstream.
Status: accepted.

## ADR-006 · 2026-09-22 · Content approval basis: published evidence, not a named human reviewer (for now)
Why: no domain reviewer available; ACSM 2026 Position Stand (MSSE, doi:10.1249/MSS.0000000000003897)
and recent meta-analyses give quantitative, citable defaults for healthy adults.
Consequences: every content parameter carries a citation and certainty grade in
`content/v1/manifest.json`; the app discloses "evidence-based, not clinician-reviewed"; scope stays
healthy adults, general resistance training. A human review can later upgrade the manifest.
Status: accepted.

## ADR-007 · 2026-09-22 · Python-maximal split
Why: owner decision (D2). Swift keeps only UI, persistence/CloudKit I/O, camera, HealthKit and
Codable DTOs; content loading, scheduling, summaries, imports, backup merge and all rules live in Python.
Consequences: Swift DTOs to be generated from a single Python-side model definition; Swift shims
(`TrainingBrain`, `ProgressionPolicy`, `PerformanceHistory`) to be removed.
Status: accepted; implementation tracked in the project plan.

## ADR-008 · 2026-09-22 · Backup via iCloud device backup now, CloudKit private-database snapshot next
Why: FigJam "backup when online" without a server. Device backup is a one-line change; CloudKit
private DB is free, per-user, and needs no infrastructure. Merge/conflict logic lives in Python.
Consequences: no cross-device live sync yet; restore is snapshot-level with explicit conflict handling.
Status: accepted.

## ADR-009 · 2026-09-22 · Shared repo for multiple coding agents
Why: owner uses both Claude and Codex. `AGENTS.md` is the single working agreement; `CLAUDE.md`
imports it. Branch prefixes identify the author; all changes via PR with green CI.
Status: accepted.
