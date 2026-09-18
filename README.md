# AI Trainer iOS

Native SwiftUI development build organized around the documented P0-P4 phases. The shared `AITrainerCore` package contains the versioned state model, local persistence, deterministic Training Brain, and behavior tests. Existing product specifications remain unchanged.

**Development preview, not an App Store release.** The repository does not contain approved training prescriptions or validated camera/recovery algorithms. Debug builds explicitly opt into numerical fixtures; Release builds reject fixture-based program activation.

## Run the app

1. Open `iOS/AITrainer.xcodeproj` directly in Xcode 16 or newer, with an iOS 17+ SDK/runtime. Keep the complete repository together. Close any other Xcode window that opened the repository folder or `Package.swift`; the app needs to load that local package itself.
2. Select the **AITrainer** scheme and an iPhone simulator. Run the **Debug** configuration.
3. Complete onboarding and explicitly accept the sample program. The initial fixture covers 2-4 available days, a repeating full-body session, and at least 41 minutes; use 60 minutes to include an optional slot and test shortening.
4. On Today, confirm your own load and available equipment values. Unknown values remain blank; the app does not infer starting strength.
5. Check in, start a workout, log sets, pause/resume, and finish. Review or correct recorded performance in History. Request progression on Today or Coach and explicitly accept the preview.
6. In Labs, enable experimental tools. Camera and real HealthKit testing require a physical iPhone. In Signing & Capabilities, choose your own team and unique bundle identifier; provisioning must support HealthKit.

No API key, paid AI service, backend, or account is required for P1. The initial build downloads the pinned MIT-licensed RepCounterSDK Swift package (Swift 6 / Xcode 16+). Runtime catalog browsing and rep counting work offline. Do not add credentials to source control.

## Troubleshooting: missing AITrainerCore

If Xcode reports `Missing package product 'AITrainerCore'`, check for an accompanying
`Couldn't load ai-trainer-ios because it is already opened from another project or workspace` error.
A separate Xcode folder/package workspace can hold the local package open, even when its window is titled `README.md`.

1. Close other Xcode windows containing this repository folder or `Package.swift`.
2. Quit Xcode, reopen it, and open only `iOS/AITrainer.xcodeproj`.
3. Choose **File > Packages > Reset Package Caches**, then **Resolve Package Versions** if needed.
4. Choose **Product > Clean Build Folder**, then build the **AITrainer** scheme for an iPhone simulator.

The project already links `AITrainerCore` through an `XCLocalSwiftPackageReference`
with `relativePath = ..`, relative to the `iOS` directory. This correctly points to the
repository-root `Package.swift`. The manifest exports the `AITrainerCore` library,
and the app lists it in both package product dependencies and its Frameworks build phase.
Do not change the reference to `../..` or add a remote package to solve a workspace conflict.

If the next error is `Unable to resolve module dependency: 'AITrainerCore'` on a
specific simulator, regenerate with the current script. Debug uses
`ONLY_ACTIVE_ARCH = YES` to match SwiftPM's active-architecture build; Release
uses `NO`. Without that alignment, an Apple Silicon simulator can build the
package for arm64 while the app also requests an unavailable x86_64 module.
Generic simulator builds can miss this mismatch because they build both architectures.

For an incomplete download, restore the full repository, including `Package.swift`
and `Sources/AITrainerCore/`. If the project file was edited, regenerate it from the repository root:

```sh
python3 scripts/generate_project.py
xcodebuild -resolvePackageDependencies -project iOS/AITrainer.xcodeproj -scheme AITrainer
```

A successful command-line build alongside a failing Xcode window can indicate an IDE
workspace/cache conflict; project regeneration alone does not close the conflicting window.

## Phase status

| Phase | Code available | Not claimed complete |
| --- | --- | --- |
| P0 | Local capture harness; measured frame throughput, latency percentiles, thermal/battery display | Physical-device benchmarks and usability validation |
| P1 | Onboarding, one sample program, manual/extra/warm-up logs, persistent rest timer, resume, corrections, audit/conflict handling, substitutions, shortening, rescheduling, progression proposals, JSON export/deletion | Reviewed content, broader splits, production SQLite/sync, cloud coach, release approval |
| P2 | Opt-in RepCounterSDK + Apple Vision 2D right-arm curl counter with confidence/visibility/dropout checks | Validated accuracy, general exercise recognition, form coaching, joint forces, automatic promotion to training evidence |
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

## Open-source integration

See [integration boundaries, licenses, and validation](docs/OPEN_SOURCE_INTEGRATION.md). Settings includes a descriptive exercise catalog and the bundled third-party notices.
