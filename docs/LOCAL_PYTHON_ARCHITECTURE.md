# Local Python architecture

## Execution and ownership

```text
SwiftUI features -> TrainerService (native persistence facade)
                   -> LocalPythonTrainerService
                        -> TrainerCoreTransport.exchange(JSON bytes)
                           EmbeddedPythonTransport -> PythonBridge C API
                             ai_trainer.api.dispatch_json
                               rules/ · commands/ · content bundle · migrations
                   <- candidate state + decision or typed error
                   -> StateRepository atomic save -> publish snapshot

Camera -> AVFoundation/Vision -> RepCounterSDK -> native observation UI
HealthKit -> native read-only provenance DTOs -> unassessed recovery response
Athlete's words -> FoundationModels (on device) -> SpokenSet draft -> readSet preview -> Save -> saveSet
Chat message -> FoundationModels (on device) -> ChatDraft -> chat reply (core-written) -> tapped action
```

CPython 3.13.11, packaged by BeeWare `3.13-b13`, runs in the app process. The
Swift package links its iOS XCFramework; the Xcode build bundles the common
standard library, architecture-specific `math`/`_json` extensions, pure Python
source, contracts and licenses. Extension modules use the PEP 730 framework and
`.fwork` layout. There is no Python executable, process spawning, loopback HTTP,
WebView interpreter, PythonKit dependency, AWS SDK, server or runtime installer.

The C bridge initializes an isolated interpreter once, disables site imports,
environment configuration and bytecode writes, adds only bundled app code, and
calls one fixed Python entry point. It never evaluates user-supplied code. It
releases the initial GIL; each invocation reacquires it, balances references,
returns owned UTF-8 memory and converts exceptions to Swift errors. A process-wide
lock serializes initialization/calls. The interpreter lives for the process lifetime.

Only `math` and `_json` native stdlib extensions are shipped. Optional database,
crypto/compression, FFI and networking binaries are excluded. Adding Python imports
that need other extensions requires explicit packaging and license review plus an
iOS smoke test. Heavyweight ML dependencies belong in `ml/`, not this runtime.

## Python package layout

See `core/python/README.md` for the module map. In short: `api.py` validates and routes;
`rules/` holds the deterministic Training Brain (eligibility gates, progression, adjustments,
program selection); `commands/` holds one handler per state mutation, including the proposal
lifecycle; `content.py` loads the bundled exercises, policy and program template;
`migrations.py` upgrades saved state; `queries.py`, `athlete_state.py`, `events.py` and
`nutrition.py` are pure helpers; `contracts.py` is the dependency-free schema validator.

## Contracts and deterministic state

`core/python/ai_trainer/{request,response}.schema.json` (generated from `contract_spec.py`)
define version **1.0**. There are sixteen operations: `stateCommand` (every mutation),
`decide` (read-only preview), `initialProgram`, `library`, `migrateState`, `nutrients`,
`recovery`, and two read-only view models for the P1 screens — `views` (Today's slot
needs-states, proposal titles and the one slot to auto-request, plus Progress's recorded
values per exercise, in one pass) and `loadSteps` (available loads around a confirmed load) — and
`readSet`, which checks the on-device model's draft of a set against the athlete's words (ADR-015).
The workout screen adds `plateLoad` (plates per side, ADR-021) and `workoutCues` (the spoken coach's
sentences, ADR-022). `chat` (ADR-023) answers a chat message: it grounds the on-device model's
`ChatDraft` in the athlete's words, and writes every line from their records, the decision a
proposal would use and the active bundle's cited values, returning the sources alongside.
`weekOptions` (ADR-017) returns up to three distinct weeks for the athlete's free weekdays and
minutes, and `initialProgram` / `acceptInitialPlan` take the chosen `optionID`. The diet screens
use `dietOptions`, `dietPreview` and `foods` (ADR-016). Requests
have `schemaVersion`, `operation` and a typed operation payload. Responses contain
that version and either a result or `{code,message}` error. The core validates its
bounded schema subset without third-party runtime dependencies. CI regenerates the
schemas and fails on drift. Unknown operations/versions,
wrong field types, malformed IDs, non-finite values and missing fields fail closed.

Dates are **binary64 seconds since 2001-01-01 UTC**, matching Foundation's existing
Codable representation. A Unix epoch conversion lost subsecond bits in unchanged
history and was deliberately rejected. Future API consumers must explicitly
convert at their boundary, not silently change this contract. IDs are UUID strings;
sets cross as arrays; absent or null optional observations remain unknown. Training
requests use explicit `kind`/named fields everywhere, including inside stored recommendations.

Time and generated IDs are supplied by the native host. The core has no clock,
randomness, persistence, network or sensor dependency. Each call owns the payload it just
parsed, so a command mutates that state in place and returns it as the candidate — nothing
the host holds is touched. `StateRepository` retains its serialized transaction,
atomic file save, data protection and publish-after-save behavior. Only a durable
host commit increments the state revision, and an unchanged candidate is not rewritten.
On launch the saved file's bytes go to `migrateState` untouched; Python upgrades older
state versions (v1 stored requests in Swift's enum shape) and validates the result before
Swift decodes it. A file that cannot be upgraded is left on disk unchanged.

### Cost per tap

Every call still carries the whole state, so cost grows with history. Measured on a Mac
(`core/python`, CPython 3.11) with a synthetic history of 12 working sets per session:
a command costs ~2 ms at 10 sessions, ~19 ms at 150 (about a year, 1.3 MB) and ~58 ms at 450;
most of that is JSON parsing and serialising, which runs in the C accelerator. The schema
validator is compiled once per schema, NaN and overflowing literals are rejected while parsing,
and Today/Progress share one `views` call, so a tap costs one command plus one view pass.
`AppStore.perform` runs both on a serial background queue and publishes on the main actor;
taps that arrive while a change is in flight are ignored. Bounding history itself (retention of
events, audits and old recommendations) needs the privacy/security decision the spec requires.

Recommendations remain proposals. Acceptance checks context/plan/policy versions,
active-session status, and re-evaluates the **stored request** against current
evidence/time. Decisions must match exactly before application. Conflicts preserve
both versions; corrections are audited; rejection does not become a preference.
Readiness stays unassessed because no reviewed recovery policy exists. Catalog
records are descriptions, separate from reviewed exercises and policy eligibility.

## What remains native

Swift owns UI/navigation, Camera/AVFoundation/Vision/CoreML runtime boundaries,
RepCounterSDK and its confidence/dropout gates, HealthKit permissions and sampling,
local persistence/data protection, Codable DTOs and read-only view projections
(calendar-day nutrient totals, rest deadlines, the next plan and active session for
display). Everything else is Python: set records are built from the slot there (context
key, unit, basis), content is loaded there, and saved files are migrated there. Swift
holds no exercise, policy or prescription values.

There are no newly implemented Watch, Live Activity, Keychain or background-task
features. If added later, their platform adapters remain Swift. High-frequency
camera frames never cross the Python boundary.

## Future API extraction

1. Publish/install `core/python` as a package. Host `dispatch_json` behind a service
   endpoint with the same versioned request/result/error DTOs; FastAPI is an option,
   not a dependency today. No domain rule needs to import a web framework.
2. Implement a remote `TrainerCoreTransport` and inject it into `LocalPythonTrainerService`
   at the `AppStore` composition root.
   Feature calls such as request/accept/log retain their facade and DTOs. Local
   preview/scaling calls in features also go through that injected service.
3. Keep local persistence/cache and explicit offline routing. Do not silently
   reinterpret remote failures as empty data or successful writes. The current
   synchronous, in-process transport must be scheduled away from the UI for remote
   work; centralize that work/completion handling at the app-store/service gateway.
4. Add authentication, transport privacy, explicit consent, idempotent commands,
   revision-based conflict checks and durable synchronization before allowing remote
   writes. A remote service must reject stale base revisions rather than overwriting
   the native snapshot. The present lock guarantees only single-process local ordering.
5. Negotiate future schema/policy versions explicitly. Keep golden contract fixtures
   and run the same domain suite against local and remote adapters.

No remote transport is implemented or selected now. API extraction is a supported
seam, not a claim that offline sync or distributed transactions are already solved.

## References

- [CPython iOS embedding and framework packaging](https://docs.python.org/3.13/using/ios.html)
- [Pinned Python Apple support release](https://github.com/beeware/Python-Apple-support/releases/tag/3.13-b13)
- [Python Apple support usage](https://github.com/beeware/Python-Apple-support/blob/3.13-b13/USAGE.md)
