# Open-source integration

The initial integration was based on `feat/native-ios-phases`. The subsequent
[local Python migration](LOCAL_PYTHON_ARCHITECTURE.md) retains both integrations.
Training/state rules now execute in Python; native perception stays Swift. The authoritative path remains:

`AthleteState -> TrainingBrain -> Recommendation -> TrainerService`

`TrainingBrain` checks profile, active session, policy approval, exercise review,
exclusions, and pain before invoking the progression policy. `TrainerService`
continues to create and apply recommendations through its existing acceptance,
evidence revision, and persistence checks. Camera observations and catalog records
never become confirmed performance or prescriptions automatically.

## Exercise descriptions

- `ExerciseCatalog` decodes all 876 records from the unchanged `dist/exercises.json`
  snapshot of [free-exercise-db](https://github.com/yuhonas/free-exercise-db), revision
  `a859101d633a01c4a1a920d6a8ce41dabba0705f`.
- It is a bundled SwiftPM resource, available offline through Settings. Malformed
  data and duplicate IDs fail loading rather than silently generating content.
- `CatalogExercise` is a separate descriptive type. No fields overwrite governed
  `Exercise` IDs, review status, role, equipment/load basis, or alternatives.
- Explicit descriptive links exist only for bench and goblet squat; other governed
  exercises remain unmapped. These links do not authorize imported instructions.
- Upstream image paths are retained as metadata. No image files are downloaded or
  distributed, and there are no automatic network requests.

## Rep counting

- SwiftPM pins [RepCounterSDK](https://github.com/NazarKozak/RepCounterSDK) at
  `94aaae70ebf30ad68522e51dd8be24f7cc793ec8`. Swift 6 tooling is required; the app and
  core keep Swift 5 language mode. Both package and Xcode resolution files are tracked.
- `CurlCounter` now wraps SDK `RepDetector`, `ExerciseSpec`, and landmark geometry.
  The custom geometry and extended/flexed counting state machine were removed.
- The adapter retains fixture thresholds (150/65 degrees), three-frame debounce,
  an initial extended baseline, 0.6–10-second durations, monotonic timestamps,
  confidence checks, and partial-rep reset after dropouts or >0.5-second gaps.
- `CameraRepTracker` centralizes Vision input validation and delegates counting to
  the SDK. `CameraService` handles capture, lifecycle, and benchmark publication.
- We intentionally use the SDK landmark API, not its convenience pixel-buffer API:
  the latter selects the first body and does not invalidate partial reps on missing
  observations. Our gate requires exactly one person and scales coordinates to
  pixels before angle calculation to preserve image aspect ratio.
- Detector access is serialized on the capture queue. `CurlCounter` is now a
  reference type because the SDK detector is stateful; do not share it across queues.
- These remain experimental observations, not technique/safety assessments. No SDK
  form messages are presented as coaching and no observations auto-log sets.

## Progression and rest/activity infrastructure

- `PerformanceHistory` extracts the existing comparable completed-session filter,
  deterministic date/ID ordering, and working-log selection.
- `DoubleProgressionPolicy` is now a Swift compatibility adapter over the Python
  implementation. The Python Training Brain owns eligibility gates and progression;
  Swift policy injection was replaced by the versioned domain service interface.
  Fixture decision order, reason strings, load steps, effort and evidence revisions
  remain covered by regression tests. No progression rules were copied
  from another repository.
- Original `WorkoutActivity` code derives a presentation snapshot from persisted
  sessions and computes rest from a deadline rather than accumulated timer ticks.
  WorkoutView uses it; rest continues while paused, matching existing behavior.
- This supplies a future ActivityKit adapter with a read-only model. It does not
  add a Live Activity/widget extension, background notifications, or Watch support.
- The existing Xcode local-package reference is sufficient for transitive SDK and
  resource linkage; project regeneration produces no project-file diff.

## Licenses

Full upstream license text is included in
[`ThirdPartyNotices.txt`](../apps/ios/Sources/AITrainerCore/Resources/ThirdPartyNotices.txt),
bundled into the app and readable in Settings:

- RepCounterSDK: MIT, Copyright (c) 2026 Nazar Kozak.
- free-exercise-db: Unlicense / public-domain dedication.

Rest/activity and progression code is original project code. No unlicensed,
AGPL, or PolyForm code was copied. No code was imported from WorkoutTracker,
openGym, wger, Onigiri, or other reference apps.

## Validation and remaining limits

- Baseline: all 47 existing package tests passed before modification.
- Integrated: all 53 package tests pass, including all 47 unchanged existing tests.
- Additional checks cover catalog loading/links/policy isolation, duplicate IDs,
  history filtering, policy injection behind pain gates, persistent rest deadlines,
  and SDK gap/out-of-order/partial-cycle behavior.
- Project regeneration produces the checked-in Xcode project exactly.
- Xcode 27.0: generic Simulator Debug, concrete iPhone Simulator Debug, and
  generic Simulator Release builds all passed with signing disabled. The only
  build warning was skipped App Intents metadata (no AppIntents dependency).
- Confirmed catalog JSON and notices are present inside the built app resource bundle.
- Real camera accuracy, orientation/device performance, and physical-device
  HealthKit/provisioning remain unvalidated; follow `DEVICE_TEST_PLAN.md`.
- Existing fixture-only training approval restrictions remain in effect.


## Embedded Python runtime

The monorepo adds CPython 3.13.11 from Python-Apple-support `3.13-b13`, with a
checksum-verified development download. The app bundles the PSF license and
Python-Apple-support MIT notice alongside the existing notices. Only CPython's
`math` and `_json` binary extensions are packaged; optional third-party
crypto/compression/FFI/database binaries are excluded. No additional code from
previously researched fitness repositories is incorporated.

The 876-record exercise JSON and pinned RepCounterSDK revision are unchanged.
Catalog validation runs in Python, but the descriptive records remain an offline
native bundle resource. Packaging and actual simulator execution are described in
[the migration report](PYTHON_MIGRATION.md).
