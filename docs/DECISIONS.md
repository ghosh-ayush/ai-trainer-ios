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
Status: implemented. DTOs are generated from `contract_spec.py` (PR #10); the shims, the
`LocalPythonTrainerService.shared` singleton and Swift-side `validate()`/`scaled(by:)` mirrors were
removed on 2026-09-23 — `AppStore` is the single composition root and Python is the only validator.

## ADR-008 · 2026-09-22 · Backup via iCloud device backup now, CloudKit private-database snapshot next
Why: FigJam "backup when online" without a server. Device backup is a one-line change; CloudKit
private DB is free, per-user, and needs no infrastructure. Merge/conflict logic lives in Python.
Consequences: no cross-device live sync yet; restore is snapshot-level with explicit conflict handling.
Status: accepted.

## ADR-009 · 2026-09-22 · Shared repo for multiple coding agents
Why: owner uses both Claude and Codex. `AGENTS.md` is the single working agreement; `CLAUDE.md`
imports it. Branch prefixes identify the author; all changes via PR with green CI.
Status: accepted.

## ADR-010 · 2026-09-23 · The owner is the legal entity for TestFlight and privacy disclosures
Why: owner decision (D7). The app is published from a personal Apple Developer account; the
privacy policy, App Privacy answers and health-data disclosures name the owner, not a company.
Consequences: no organisation-level review gate exists, so the evidence manifest (ADR-006) and the
in-app "evidence-based, not clinician-reviewed" disclosure carry the compliance story. Revisit if a
company entity is created or the app leaves TestFlight.
Status: accepted.

## ADR-011 · 2026-09-23 · Xcode owns `AITrainer.xcodeproj`; the project generator is retired
Why: `scripts/generate_project.py` had drifted from the Xcode-normalised project (it dropped the
"Bundle local Python" build phase) and its CI step re-ran it on every build, so a green run
depended on nobody having touched the project in Xcode. Two writers for one file is one too many.
Consequences: app-target files are added through Xcode; package files under `apps/ios/Sources`
and `apps/ios/Tests` need no project edit. The generator and its CI step are deleted. When the
app target grows past a handful of files, switch it to an Xcode folder-synchronised group so new
files stop requiring a `pbxproj` change at all.
Status: accepted.

## ADR-012 · 2026-09-23 · Content, set records and state migration move into Python; one command path
Why: owner request to make the codebase as Python as possible and remove clutter. Swift still held
fixture exercises and policy values, built set records (including the comparison key), sent the
whole content library on every call, and kept a second dispatch path for recommendations plus a
Swift-enum-shaped stored request that Python had to translate.
Consequences: training content (exercises, policy and the program template's sets/reps/rest/minutes)
ships as `ai_trainer/fixture_content.json`; the host sends only `permitsFixtures`. `saveSet` takes
what the athlete entered and Python builds the record. Recommendations are ordinary state commands
(`requestChange`, `acceptRecommendation`, `rejectRecommendation`). Stored requests use the explicit
`{kind, …}` shape; state schema version 2, with `migrateState` upgrading v1 files in Python before
Swift decodes them. Unused operations (`progression`, `performance`, `workingLogs`, `validateSet`,
`catalog`, `recommendation`), the `ai_trainer.service` alias, the `TrainerDomainService` protocol and
the duplicate `shared/schemas` copy are gone. Rule tests live in Python; Swift tests cover transport,
persistence, migration wiring, perception and one end-to-end flow. Contract version stays 1.0.
Status: accepted.

## ADR-013 · 2026-09-23 · P1 UX simplification ships with the Stitch kit and three OFL fonts
Why: owner request to implement the Figma "Proposed P1 flow — simplified" (3 tabs, no check-in,
one-tap set logging, proposals and needs-states on the slot card). The design's type system uses
Space Grotesk, Inter and JetBrains Mono, all SIL OFL-1.1, which rule 5 did not allow; the owner
chose to bundle them rather than substitute SF Pro / SF Mono.
Consequences: AGENTS.md rule 5 now permits OFL-1.1 fonts bundled unmodified; the five font files
live in the package resources with their licenses in ThirdPartyNotices.txt and are registered at
launch. The Stitch components live in `AITrainerCore/Stitch.swift` (package files need no Xcode
project edit). Tabs are Today · Progress · You; Coach folds into Today, Labs moves to You ▸
Developer (Debug only). New read-only core operations `todayStatus`, `progress` and `loadSteps`
keep the screens' logic in Python; no engine rule changed. Today auto-requests at most one
progression proposal, never re-proposes one the athlete rejected in the same context, and still
applies nothing without Accept.
Status: accepted.
