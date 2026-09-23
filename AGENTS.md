# AGENTS.md — working agreement for humans and coding agents (Claude, Codex, others)

This file is the single source of truth for how to work in this repository.
`CLAUDE.md` imports it; Codex reads it directly. Keep the two in sync by editing only this file.

## What this project is
AI Trainer: a local-first iPhone resistance-training app. Domain rules run in **embedded CPython**
(`core/python/ai_trainer`); Swift owns UI, persistence, camera, HealthKit (`apps/ios`). No backend,
no network at runtime, no LLM in the decision path. Product spec: `docs/AI_Trainer_01_*.md`.
Architecture: `docs/LOCAL_PYTHON_ARCHITECTURE.md`. Decisions: `docs/DECISIONS.md`.

## Non-negotiable rules
1. **Never invent training content.** Exercises, templates, rep/set/RIR/rest values and progression
   parameters ship only from a content bundle whose `manifest.json` cites its evidence basis.
   Fixture values are test data; they must not become defaults. Release builds refuse
   `review: fixture` content — keep it that way.
2. **Unknown stays unknown.** `load`, `rir`, effort and any sensor-derived value are optional.
   Never default them to favourable values or estimate strength.
3. **Proposals, not mutations.** Any plan change is a `Recommendation` that the user explicitly
   accepts. Acceptance re-evaluates the stored request and requires an identical decision.
4. **Sensors never write evidence.** Camera, HealthKit, catalog and nutrition data must not feed
   progression or become `SetLog` records.
5. **Licenses.** Only MIT / BSD / Apache-2.0 / Unlicense / public-domain / CC0 code and data.
   No AGPL, GPL, LGPL, SSPL, PolyForm, CC-BY-SA data, or unlicensed datasets — not even as a
   reference implementation to copy from. Add every new dependency or dataset to
   `apps/ios/Sources/AITrainerCore/Resources/ThirdPartyNotices.txt`.
6. **Python first.** New logic goes in `core/python` unless it is UI, per-frame perception,
   platform I/O (files, CloudKit, HealthKit, camera) or a Codable DTO. Swift is a thin client.
7. **No secrets, no credentials, no personal health data** in the repo, fixtures or tests.

## Repository map
```
core/python/ai_trainer/   domain rules, state commands, recommendation lifecycle, contracts
core/python/tests/        Python behaviour + contract tests (fast; run these constantly)
shared/schemas/v1/        contract v1.0 JSON schemas (generated; do not hand-edit)
shared/fixtures/v1/       golden request/response fixtures
apps/ios/App/             SwiftUI app + GENERATED AITrainer.xcodeproj
apps/ios/Sources/AITrainerCore/   Swift DTOs, transport to Python, persistence, perception
apps/ios/PythonBridge/    C bridge to CPython (rarely changes)
apps/ios/Vendor/          gitignored: Python.xcframework from scripts/setup_python.sh
scripts/                  setup, bundling, generation, tests, simulator smoke
docs/                     spec, architecture, migration notes, device test plan, ADRs
```

## Setup (once per clone)
```
scripts/setup_python.sh                 # downloads the pinned CPython xcframework (macOS)
```
Nothing in `apps/ios` builds until that has run.

## Commands
```
PYTHONPATH=core/python python3 -m unittest discover -s core/python/tests -v   # Python tests (Linux/macOS)
scripts/test.sh                          # Python + Swift tests through embedded CPython (macOS)
python3 scripts/generate_schemas.py      # after ANY change to contract shapes; CI diffs the output
python3 scripts/generate_project.py      # after adding/removing/renaming Swift files; CI diffs the output
open apps/ios/App/AITrainer.xcodeproj    # scheme AITrainer, Debug, iPhone simulator
scripts/smoke_ios.sh <BOOTED_SIM_UUID>   # after a Debug build
```

## Workflow
- Branch per task: `claude/<topic>`, `codex/<topic>`, `feat/<topic>`. Never commit to `master`.
- One PR per change; CI (`python`, `swift-tests` and `simulator` jobs) must be green; squash-merge.
- Definition of done: tests added/updated · schemas regenerated if contracts changed · project
  regenerated if Swift files changed · docs touched if behaviour changed · ADR in
  `docs/DECISIONS.md` if an architectural or product-policy decision was made · notices updated
  if a dependency was added.
- Keep the Swift⇄Python contract at version `1.0` unless an ADR says otherwise.
- Prefer small, readable code over clever one-liners. Descriptive names; a docstring per public
  function; no semicolon-chained statements. Agents: do not compress code to save tokens.
- Do not run `rm -rf` on `apps/ios/Vendor` or `DerivedData` in someone else's checkout.

## Things that look like bugs but are intentional
- Release builds cannot activate a plan (no approved content yet).
- Recovery observations always return `unassessed` (no reviewed readiness policy).
- Curl counter reps are never saved as sets.
- Dates cross the bridge as binary64 seconds since 2001-01-01 (Foundation reference epoch).
