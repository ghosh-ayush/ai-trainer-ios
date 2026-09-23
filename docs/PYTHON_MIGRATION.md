# Python monorepo migration

## Base and layout

Started from `feat/open-source-integration` at `1f1e000`, derived from
`feat/native-ios-phases`. Work is on `feat/local-python-monorepo`, stacked on the
open-source integration branch so that PR #3's catalog/perception changes remain
intact. `master` was not changed. The pre-existing uncommitted Xcode project
normalization was carried forward; project path and packaging changes were applied
to that file without resetting it. Original product specification files are unchanged.

Native source/tests moved under `apps/ios/`; the app project is now
`apps/ios/App/AITrainer.xcodeproj`. Root `Package.swift` keeps one native package entry
point. `core/python`, `shared/schemas`, `ml`, and migration documentation are new.

## Moved behavior

| Previous Swift responsibility | Python owner / behavior |
| --- | --- |
| `TrainingBrain.decide` | `domain.decide`: profile/session/review gates, pain/exclusions, progression, shortening, curated substitution and rescheduling |
| `ContentLibrary.initialProgram` | `domain.initial_program`: supported profile scope, role/equipment selection and preference ordering; host supplies IDs |
| `DoubleProgressionPolicy` | `domain.progression`: exact comparable evidence, stale/gap rules, RIR unknowns, rep targets, available steps and bounded increases |
| `TrainerService` mutations | `state.reduce_state`: plan/load setup, check-in, workout start/pause/finish/skip, idempotent set logging, exclusions, correction/conflict resolution and deletion |
| Recommendation lifecycle | `service.recommendation_command`: proposals, reject/accept, version checks, stored-request re-evaluation and audit events |
| Set validation | `state.validate_set`: reps/index/RIR/load validation |
| Meal lifecycle | `state.reduce_state`: revisions, correction audit, recipe creation and deletion |
| Nutrient validation/scaling | `service.nutrients`: finite/nonnegative validation, servings and overflow |
| Catalog content validation | `service.dispatch` catalog operation: typed schema and duplicate-ID checks, with no promotion to reviewed policy |
| Recovery boundary | Explicit `unassessed` response over read-only source/time observations; no invented readiness algorithm |

The native `TrainerService` is now a persistence/service facade. Swift retains
Codable structs and existing state-file compatibility, atomic protected local saves,
small display/calendar/value projections, SwiftUI, HealthKit, camera/Vision,
RepCounterSDK and timing-sensitive processing. No new live camera Python loop was
introduced. Watch, Live Activities and CoreML export are future work, not newly
implemented features.

## Interop

Use CPython's official C API, an iOS XCFramework and PEP 730 extension packaging.
The Swift `TrainerDomainService` protocol and `TrainerCoreTransport` JSON seam are
explicit substitution points. There is no HTTP dependency or required connection.
The small bridge owns GIL/refcount/string lifetime and propagates errors. Python
modules and versioned schemas are bundled in the signed app; they are not downloaded
or changed at runtime. `ml/` is intentionally only an integration guide until there
is an actual model/export task.

## Verification

- 27 Python unit/contract tests, including unknowns, pain/review gates, exact golden
  decisions, stale evidence, proposal/accept/reject, pure state transitions,
  correction conflicts, meal audits, invalid contracts, catalog and recovery.
- 59 Swift tests through the real embedded desktop C bridge: all 47 original
  trainer tests plus native/catalog/perception integration and six new contract,
  timestamp, concurrency and persistence-failure tests.
- The previous Swift policy-injection test was updated for Python ownership while
  retaining the test that pain blocks an otherwise qualifying progression.
- Xcode Debug simulator build and actual iPhone 17 Pro / iOS 26.2 runtime smoke:
  plan creation, two exposures, progression proposal and explicit application to
  105, nutrition scaling and 876-record catalog loading passed.
- The runtime smoke was repeated after restricting bundled extensions to `math`
  and `_json`; it passed with the app's actual embedded CPython 3.13.11.

- Xcode 27.0 Release simulator build passed for both arm64 and x86_64.
- Unsigned Release build for the generic iPhone device target passed, including
  device CPython linking and packaging. This is compilation, not a device run.
- Setup archive checksum, generated project syntax, Python syntax, unchanged
  exercise-catalog SHA-256 and whitespace checks passed.

CI is configured for Python, embedded Swift tests, a simulator runtime smoke and
Release build. See the PR for its separately reported hosted CI status. Build
success does not constitute physical-device or App Store validation.

## Remaining limitations

- No physical iPhone execution, provisioning/archive upload, camera accuracy,
  HealthKit source validation, battery/thermal or App Store review was performed.
- Existing fixture-only training content remains unapproved; Release refuses fixture
  activation. Broader training, form assessment and readiness algorithms are absent.
- The boundary currently serializes whole state and runs synchronously at coarse
  user actions. Large histories need profiling, bounded queries and background
  scheduling at the central store/service gateway. It must never run per camera frame.
- Remote API extraction still requires remote scheduling, authentication, consent,
  idempotency and revision-aware offline synchronization. The DTO/service seam is
  ready; a production network service is not implemented.
- Pure Python core tests are portable; Swift embedding tests require macOS, matching
  desktop Python headers/libpython and the supplied test script. iOS builds require
  one development-time pinned framework/Swift-package download, or pre-cached copies.
- Runtime framework binaries are intentionally not committed. Run the setup script
  before Xcode resolves the local package. The framework adds app size/startup cost;
  no low-memory-device performance claim is made.
- Optional stdlib extensions are excluded. Future imports/model runtimes need an
  explicit extension/dependency/license update and simulator/device verification.
