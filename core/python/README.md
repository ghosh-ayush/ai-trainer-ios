# `ai_trainer` — the deterministic training core

Pure Python, no third-party runtime dependencies, no clock, no random IDs, no I/O.
The Swift host supplies `now` and every UUID; the core returns a *candidate* state and
the host commits it atomically. Runs identically on Linux CI, a Mac, and inside the app's
embedded CPython.

## Module map

```
ai_trainer/
├── api.py                 dispatch_json / dispatch — the C bridge's entry point; validates and routes
├── contracts.py           bounded JSON-Schema validator + bundled request/response schemas
├── errors.py              DomainError(code, message) + require()
├── messages.py            decision(reason, …) builder; reason → outcome/explanation table
├── decisions.json         the reason codes and their user-facing explanations
├── athlete_state.py       read-only accessors: next_plan, active_session, comparison_key, …
├── events.py              record_event, expire_proposals, store_plan
├── content.py             loads the content bundle; ReviewStatus gating: is_enabled, exercises_by_id
├── fixture_content.json   exercises, progression policy and program template (review: fixture)
├── migrations.py          upgrades saved state files to the current state schema version
├── queries.py             comparable_sessions, working_logs, evidence_from
├── nutrition.py           validate_nutrients, scale_nutrients
├── rules/
│   ├── eligibility.py     decide(): spec §5.2 gate order, then routes to a rule
│   ├── progression.py     TB-04 double progression on comparable evidence
│   ├── adjustments.py     TB-02/03/06 reschedule · shorten · curated substitution
│   ├── program.py         TB-01 initial program selection (one-session template, or the weekly planner)
│   ├── selection.py       exercise for a role, per-goal prescription (shared by both program paths)
│   ├── week_plans.py      ADR-017: every week the guardrails allow on the athlete's free days
│   ├── plan_ranking.py    ADR-017: orders valid weeks for one athlete, with reason codes
│   └── week_program.py    ADR-017: distinct options, and the Program the chosen one becomes
└── commands/
    ├── __init__.py        reduce_state(payload): command → handler table
    ├── context.py         CommandContext: state copy, arguments, now, id supply, event helper
    ├── plan.py            acceptInitialPlan · configureLoad
    ├── workout.py         start · skip · setPaused · saveSet · finish · reportPain · exclude
    ├── records.py         correctSet · resolveConflict · deleteSession
    ├── meals.py           saveMeal · deleteMeal
    └── proposals.py       requestChange · acceptRecommendation · rejectRecommendation
```

## Reading order for a newcomer

1. `api.py` — what operations exist and how errors come back.
2. `rules/eligibility.py` — the gate order every request passes.
3. `rules/progression.py` — the one non-trivial algorithm.
4. `commands/workout.py` — how a session is recorded.
5. `commands/proposals.py` — why nothing changes without acceptance.

## Invariants (enforced by tests)

- Unknown `load` / `rir` are absent keys, never zeros or guesses.
- A proposal pins context revision, plan id/revision and policy version; acceptance
  re-evaluates the stored request and requires an identical decision.
- Any state mutation expires pending proposals.
- Camera, HealthKit, catalog and meals never feed progression.
- `revision` is incremented by the host on durable commit, never here.

## Commands

```
PYTHONPATH=core/python python3 -m unittest discover -s core/python/tests -v
cd core/python && ruff check . && ruff format --check . && mypy
python3 scripts/generate_schemas.py      # after any contract change; CI diffs the output
```
