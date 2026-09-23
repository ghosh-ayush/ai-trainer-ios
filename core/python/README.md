# `ai_trainer` — the deterministic training core

Pure Python, no third-party runtime dependencies, no clock, no random IDs, no I/O.
The Swift host supplies `now` and every UUID; the core returns a *candidate* state and
the host commits it atomically. Runs identically on Linux CI, a Mac, and inside the app's
embedded CPython.

## Module map

```
ai_trainer/
├── api.py                 dispatch_json / dispatch — validate the envelope, route the operation
├── service.py             alias of api (the C bridge imports ai_trainer.service.dispatch_json)
├── contracts.py           bounded JSON-Schema validator + bundled request/response schemas
├── errors.py              DomainError(code, message) + require()
├── messages.py            decision(reason, …) builder; reason → outcome/explanation table
├── decisions.json         the 32 reason codes and their user-facing explanations
├── athlete_state.py       read-only accessors: next_plan, active_session, comparison_key, …
├── events.py              record_event, expire_proposals, store_plan
├── content.py             ReviewStatus gating: is_enabled, exercises_by_id
├── queries.py             comparable_sessions, working_logs, evidence_from
├── nutrition.py           validate_nutrients, scale_nutrients
├── recommendations.py     request → proposed → applied | rejected | expired
├── rules/
│   ├── eligibility.py     decide(): spec §5.2 gate order, then routes to a rule
│   ├── progression.py     TB-04 double progression on comparable evidence
│   ├── adjustments.py     TB-02/03/06 reschedule · shorten · curated substitution
│   └── program.py         TB-01 initial program selection
└── commands/
    ├── __init__.py        reduce_state(payload): command → handler table
    ├── context.py         CommandContext: state copy, arguments, now, id supply, event helper
    ├── plan.py            acceptInitialPlan · configureLoad
    ├── workout.py         start · skip · setPaused · saveSet · finish · reportPain · exclude
    ├── records.py         correctSet · resolveConflict · deleteSession
    └── meals.py           saveMeal · deleteMeal
```

## Reading order for a newcomer

1. `api.py` — what operations exist and how errors come back.
2. `rules/eligibility.py` — the gate order every request passes.
3. `rules/progression.py` — the one non-trivial algorithm.
4. `commands/workout.py` — how a session is recorded.
5. `recommendations.py` — why nothing changes without acceptance.

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
