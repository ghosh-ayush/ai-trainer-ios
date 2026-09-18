# AI Trainer iOS

Native SwiftUI development build organized around the documented P0-P4 phases. The shared `AITrainerCore` package contains the versioned state model, local persistence, deterministic Training Brain, and behavior tests. Existing product specifications remain unchanged.

**Development preview, not an App Store release.** The repository does not contain approved training prescriptions or validated camera/recovery algorithms. Debug builds explicitly opt into numerical fixtures; Release builds reject fixture-based program activation.

## Run the app

1. Open `iOS/AITrainer.xcodeproj` in Xcode 16 or newer, with an iOS 17+ SDK/runtime.
2. Select the **AITrainer** scheme and an iPhone simulator. Run the **Debug** configuration.
3. Complete onboarding and explicitly accept the sample program. The initial fixture covers 2-4 available days, a repeating full-body session, and at least 41 minutes; use 60 minutes to include an optional slot and test shortening.
4. On Today, confirm your own load and available equipment values. Unknown values remain blank; the app does not infer starting strength.
5. Check in, start a workout, log sets, pause/resume, and finish. Review or correct recorded performance in History. Request progression on Today or Coach and explicitly accept the preview.
6. In Labs, enable experimental tools. Camera and real HealthKit testing require a physical iPhone. In Signing & Capabilities, choose your own team and unique bundle identifier; provisioning must support HealthKit.

No API key, paid AI service, package download, backend, or account is required for P1. Do not add credentials to source control.

## Phase status

| Phase | Code available | Not claimed complete |
| --- | --- | --- |
| P0 | Local capture harness; measured frame throughput, latency percentiles, thermal/battery display | Physical-device benchmarks and usability validation |
| P1 | Onboarding, one sample program, manual/extra/warm-up logs, persistent rest timer, resume, corrections, audit/conflict handling, substitutions, shortening, rescheduling, progression proposals, JSON export/deletion | Reviewed content, broader splits, production SQLite/sync, cloud coach, release approval |
| P2 | Opt-in Apple Vision 2D right-arm curl counter with confidence/visibility/dropout checks | Validated accuracy, general exercise recognition, form coaching, joint forces, automatic promotion to training evidence |
| P3 | Opt-in read-only HealthKit HRV SDNN, resting HR, and individual sleep samples with source/time | Baselines, readiness scores, wearable-driven program adjustments, weather integration |
| P4 | Manual meal estimates, corrections, reusable portions, portion scaling, local daily totals | Food database, photo identification, calibrated volume, nutrition-driven training |
| R | Explicitly excluded from the guidance path | Inverse dynamics, lumbar forces, injury-risk claims, food geometry |

See [implementation and release gaps](docs/IMPLEMENTATION.md) and [physical-device checklist](docs/DEVICE_TEST_PLAN.md).

## Tests and builds

The core has no Apple-framework dependency and can be tested on Linux or macOS:

```sh
swift test
```

Regenerate the checked-in Xcode project after adding or removing native Swift files:

```sh
python3 scripts/generate_project.py
```

Compile the iOS app on a Mac:

```sh
xcodebuild -project iOS/AITrainer.xcodeproj -scheme AITrainer \
  -configuration Debug -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build
```

CI runs core tests and Debug/Release simulator builds. Passing core tests is not proof of native UI correctness, sensor accuracy, or training effectiveness. Native hardware testing and content review remain required.

## Structure

```text
Sources/AITrainerCore/         Domain models, policies, transactions, experiments
Tests/AITrainerCoreTests/      Executable behavior and regression tests
iOS/AITrainer/App/             SwiftUI entry point and presentation store
iOS/AITrainer/Features/        Onboarding, Today, workout, History, Coach, Labs
iOS/AITrainer/Services/        AVFoundation/Vision and HealthKit adapters
iOS/AITrainer/Resources/       Permission descriptions, entitlements, privacy manifest
iOS/AITrainer.xcodeproj/       Shared Xcode project and scheme
scripts/generate_project.py   Dependency-free project generator
docs/                         Product specification, implementation notes, device tests
```

## Documentation

**01. Athlete State + Training Brain**, version 0.1, September 17, 2026: proposed specification for product, training-domain, design, and engineering review.

- [Read the original specification](docs/AI_Trainer_01_Athlete_State_and_Training_Brain.md)
- [Download the original Word specification](docs/AI_Trainer_01_Athlete_State_and_Training_Brain.docx)

Detailed rules and numerical fixtures are proposals and test cases, not approved production training prescriptions. The implementation notes explicitly identify narrower coverage and deviations rather than treating the entire roadmap as shipped.
