# Historical native implementation notes

These notes describe the original native implementation. See [the Python migration](PYTHON_MIGRATION.md) and [current architecture](LOCAL_PYTHON_ARCHITECTURE.md) for the monorepo runtime, current tests, paths and ownership.

# Phase-based iOS implementation

Implementation snapshot: September 17, 2026. Basis: the existing **01. Athlete State + Training Brain v0.1** and its P0-P4/R phase boundaries. This is a development build, not release approval.

## Design choices made for this implementation

The original concept mentioned React Native/Expo, web inference, Wasm, and SQLite. This implementation deliberately uses native SwiftUI, a pure Swift domain package, Apple Vision/AVFoundation, and a transactional JSON snapshot adapter. This is an implementation proposal for the requested iOS app, not an assertion that the original technical stack was already changed or approved.

The `StatePersistence` interface isolates storage. Before a multi-device production release, replace the snapshot adapter with a reviewed database and migration design. JSON whole-state rewrites are suitable for exercising this small prototype, not a claim of production-scale storage performance. There is no cloud sync, server, restore endpoint, authentication, remote analytics SDK, or language-model integration.

## P1 architecture and traceability

| Specification area | Implementation |
| --- | --- |
| Four separate state layers | Profile/SetLog, summaries calculated on demand, Program/Recommendation, explicit preferences |
| Unknown values | Optional load and RIR; never favorable defaults |
| Context-specific history | Variant, equipment identity, unit/basis, protocol and rep convention in comparison key |
| Transactional persistence | StateRepository copies state, validates mutation, persists, then publishes; errors retain prior state |
| AS-03 duplicate retry | Stable operation ID; reused IDs with changed payload rejected |
| AS-04 corrections | Revision check, previous set audit, pending-proposal expiry |
| AS-05 interruption | Entire active session, accepted plan, logs and absolute rest-end timestamp are persisted |
| AS-06 conflict | Competing set revisions are retained for explicit resolution; no silent winner. Network synchronization is not implemented. |
| AS-07 program changes | Completed sessions embed their own plan and program revision; old programs retained |
| AS-08 deletion | Session deletion removes dependent records; delete-all replaces local state. No restore/backup endpoint exists. Externally exported files remain the user's responsibility. |
| TB-01 selection | One explicitly accepted repeating full-body fixture; no reviewed commercial library |
| TB-02 missed work | Explicit reschedule or skip, separate sequence index, no automatic doubled volume |
| TB-03 shorter sessions | Remove optional slots only; no compression of required rest/warm-up |
| TB-04 progression | Context/evidence checks, consecutive exposure count, history/gap limits, one available bounded load step, single-total-rep allocation |
| TB-05 intra-session | Active plan pinned; next-plan proposals withheld while any workout is active |
| TB-06 substitution | Directional catalog entries; exclusion/equipment filtering; baseline is cleared rather than transferred |
| TB-07 subjective check-in | Energy/soreness recorded without scoring or automatic volume changes |
| TB-08 concern | Reported pain persists as an exclusion and pauses the workout; no diagnosis or clearance |
| TB-09 preference | Rejection reason recorded without inferred dislike. Automatic learning is not implemented. |
| TB-10 review | Domain supports replacing an accepted program while retaining prior versions; full goal-change/review UX is deferred |
| Recommendation lifecycle | Preview, re-evaluate on accept, atomically apply once; reject/expire supported |
| AI boundary | Structured local Coach actions only. No LLM can write records because no LLM adapter is connected. |

### Important narrower coverage

The catalog contains eight **unreviewed fixture exercises**. One repeating full-body template is available in Debug. It is not a full split/program library; available-days input is retained but does not create a recurring calendar schedule. Exercise instructions, lighter alternatives, initial-load familiarization, concern-resolution copy, and production prescription parameters need training-domain review.

The `DP_TEST_01` behavior exercises the document's 3-set, 8-10-rep, RIR-2, two-exposure, 5%-maximum fixture. The added 28-day history and 14-day gap values are **implementation fixtures**, not inherited clinical rules. Machine settings and assistance do not receive this external-load progression policy. Real starting loads and equipment steps are not prefilled.

Substitution presently clears the baseline even when an alternative has history. It does not yet automatically select/reconfirm the substitute's own prior baseline. Program-level deload/review algorithms, skill/familiarity ranking, multiple-location inventory management, rich body-region constraints, and automatic outcome learning are deferred. Persistent pain restrictions cannot be cleared through a medical-clearance claim in this prototype.

Current analytics remain inside the local state file. They exercise selected controlled event names; there is no production cohort pipeline or complete event-envelope implementation. Evidence summaries are computed on demand rather than materialized in an independent summary table. Full retention, account deletion, backup expiry, and migration policies remain release work.

## P0 and P2

`CameraService` runs AVFoundation frames on a serial queue, discards late frames, and performs Apple's `VNDetectHumanBodyPoseRequest`. It processes a single detected person and right shoulder/elbow/wrist points. Coordinates are scaled by actual pixel-buffer dimensions before computing a 2D angle.

`CurlCounter` uses hysteresis, three-frame confirmation, monotonic sample timestamps, dropout reset, and duration bounds. Its 0.5 landmark cutoff, 150/65 degree thresholds, 0.5-second gap and 0.6-10-second duration bounds are experimental fixtures. They are not calibrated probabilities, a release support matrix, or technique/safety criteria. Occlusion or extra people produce unassessed output. Idle extension is excluded from cycle timing. A missing observation cannot complete a partial repetition.

The camera lab does not save video, measure actual lumbar force, infer effort, issue safety cues, or promote inferred reps to authoritative SetLog records. It has no general exercise recognition. P0 surfaces measured diagnostic performance, not a claim of 60 FPS or zero latency. Device-level validation remains unperformed until the checklist is executed.

## P3

The read-only HealthKit adapter requests HRV SDNN, resting heart rate and sleep samples only after explicit user action. It reads at most 300 samples per type, with 28-day HRV/RHR and 7-day sleep windows. Source and time remain visible. Individual sleep records are displayed rather than incorrectly summed across devices or overlapping categories.

Permission-request completion is not treated as proof of read access. An empty query is described as no readable samples: missing data, permission restrictions and limited access cannot be safely distinguished here. No health data is written. Raw readings remain in the recovery screen's memory, are cleared on exit, and are never sent to the training rules as evidence. Baseline computation, sufficiency rules, accepted adaptive changes and weather remain unimplemented pending a reviewed policy.

## P4

Manual meal estimates require explicit calories/protein/carbs/fat and portion confirmation. Saved portions are immutable nutrient snapshots; scaling multiplies that snapshot by a confirmed number of portions. Daily totals use the device calendar. Meals carry original time-zone metadata, but travel-aware historic-day regrouping is not implemented.

Corrections retain the preceding meal revision and reject a stale edit. Meal deletion removes its correction records. Saved portions are separate records, not automatically changed when an old meal is corrected. There is no verified food database, photo identification, exact portion/volume inference, automatic macro target, or nutrition-driven training adjustment.

## Storage and permission boundaries

On iOS, the state directory and atomic writes use complete file protection. The directory is included in iOS device backups (iCloud Backup and computer backups) by default; Settings → "Include in iPhone backups" excludes it, and the preference is only recorded after the file-system attribute changed. Restoring a backup restores the file as it was; there is no merge, so a restore can resurrect records deleted after the backup was made (ADR-008 tracks the CloudKit snapshot that will add explicit conflict handling). Unlock is required to access the protected file; startup errors never reset the file. Export is explicit, local JSON and contains sensitive user records. There is no import endpoint to resurrect deleted data. This is logical application deletion, not a promise about forensic erasure of device storage or exported copies.

Camera permission is separate from HealthKit authorization and from enabling experimental tools. No microphone, precise location, advertising, tracking, research upload, or model-training consent is requested because those features are absent. The privacy manifest is a starting declaration for this build and requires a fresh audit before distribution or adding dependencies.

## Verification

Run `swift test` for the package's behavior suite. The initial local environment is Linux with Swift 6.2.1: domain code is executable there, native iOS frameworks are not. Swift parser validation does not replace an iOS SDK build. GitHub Actions is configured to run core tests and compile Debug/Release iOS Simulator variants on macOS. Consult actual CI results before claiming native build success. No simulator-interaction, accessibility, battery, camera accuracy, or physical-device result is implied by compilation.

## API references checked during implementation

- Apple Vision body-pose types: https://developer.apple.com/documentation/vision/vnrecognizedpointsobservation
- Vision request algorithm revision: https://developer.apple.com/documentation/vision/vnrequest/revision
- HealthKit authorization semantics: https://developer.apple.com/documentation/healthkit/authorizing-access-to-health-data
- HealthKit write-vs-read permission status: https://developer.apple.com/documentation/healthkit/hkhealthstore/authorizationstatus(for:)
- Swift documentation/testing: https://docs.swift.org/
- Privacy manifest required-reason APIs: https://developer.apple.com/documentation/bundleresources/describing-use-of-required-reason-api

These references support API usage only. They do not validate the training fixture, camera thresholds, readiness algorithms, or clinical claims.
