# Local Python architecture

## Execution and ownership

```text
SwiftUI features -> TrainerService (native persistence facade)
                   -> TrainerDomainService
                      LocalPythonTrainerService
                        -> TrainerCoreTransport.exchange(JSON bytes)
                           EmbeddedPythonTransport -> PythonBridge C API
                             ai_trainer.api.dispatch_json  (ai_trainer.service is an alias)
                               rules/ · commands/ · recommendations.py · queries.py
                   <- candidate state + decision or typed error
                   -> StateRepository atomic save -> publish snapshot

Camera -> AVFoundation/Vision -> RepCounterSDK -> native observation UI
HealthKit -> native read-only provenance DTOs -> unassessed recovery response
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
program selection); `commands/` holds one handler per state mutation; `recommendations.py`
owns the proposal lifecycle; `queries.py`, `athlete_state.py`, `events.py`, `content.py` and
`nutrition.py` are pure helpers; `contracts.py` is the dependency-free schema validator.

## Contracts and deterministic state

`shared/schemas/v1/{request,response}.schema.json` define version **1.0**. Requests
have `schemaVersion`, `operation` and a typed operation payload. Responses contain
that version and either a result or `{code,message}` error. The core validates its
bounded schema subset without third-party runtime dependencies. Schemas copied into
the Python package are generated and checked for drift. Unknown operations/versions,
wrong field types, malformed IDs, non-finite values and missing fields fail closed.

Dates are **binary64 seconds since 2001-01-01 UTC**, matching Foundation's existing
Codable representation. A Unix epoch conversion lost subsecond bits in unchanged
history and was deliberately rejected. Future API consumers must explicitly
convert at their boundary, not silently change this contract. IDs are UUID strings;
sets cross as arrays; absent or null optional observations remain unknown. The
persisted `Request` enum retains its original Codable tagged shape inside historical
recommendations, while operation requests use explicit `kind`/named fields.

Time and generated IDs are supplied by the native host. The core has no clock,
randomness, persistence, network or sensor dependency. It deep-copies state before
mutating, returning a candidate. `StateRepository` retains its serialized transaction,
atomic file save, data protection and publish-after-save behavior. Only a durable
host commit increments the state revision. Existing schemaVersion 1 saved files
are read/written with the unchanged reference-epoch format; no destructive data
migration is needed.

Recommendations remain proposals. Acceptance checks context/plan/policy versions,
active-session status, and re-evaluates the **stored request** against current
evidence/time. Decisions must match exactly before application. Conflicts preserve
both versions; corrections are audited; rejection does not become a preference.
Readiness stays unassessed because no reviewed recovery policy exists. Catalog
records are descriptions, separate from reviewed exercises and policy eligibility.

## What remains native

Swift owns UI/navigation, Camera/AVFoundation/Vision/CoreML runtime boundaries,
RepCounterSDK and its confidence/dropout gates, HealthKit permissions and sampling,
local persistence/data protection, Codable DTOs and view projections. Existing
small value projections remain Swift: equipment comparison keys, unit conversions,
calendar-day selection and addition of already-confirmed nutrient values, display
rest deadlines, and read-only history views. The authoritative progression algorithm
and comparable-evidence selection run in Python. Fixture content DTO declarations
remain shared with native presentation, not a second policy engine.

There are no newly implemented Watch, Live Activity, Keychain or background-task
features. If added later, their platform adapters remain Swift. High-frequency
camera frames never cross the Python boundary.

## Future API extraction

1. Publish/install `core/python` as a package. Host `dispatch_json` behind a service
   endpoint with the same versioned request/result/error DTOs; FastAPI is an option,
   not a dependency today. No domain rule needs to import a web framework.
2. Implement `RemoteTrainerService: TrainerDomainService` or a remote
   `TrainerCoreTransport`, and inject it at the `TrainerService` composition root.
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
