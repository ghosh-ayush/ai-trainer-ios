# AI Trainer
## 01. Athlete State + Training Brain

Product and functional specification | Version 0.1 | September 17, 2026

**Decision status:** Proposed specification for product, training-domain, design, and engineering review.

**Core contract:** Athlete State records what is known about a person and their training. The Training Brain uses that state, approved exercise content, and explicit policies to propose the next action. A recommendation must never become a recorded fact merely because the system generated it.

## 1. Purpose, scope, and source alignment

The product must answer two questions: **What does this trainer know about this person?** and **How does that information change their next workout?** This specification defines the shared data model and the P1 decision behavior behind onboarding, initial plans, workout execution, curated substitutions, history, and progression.

The FigJam board already contains this P1 loop: goals, experience, equipment, schedule, initial plan, Today, energy and soreness, workout, session summary, history, and next-session updates. It also explicitly includes manual logging, local storage, privacy, and backup. [S2: 1:9-1:44; 5:503]

### 1.1 Requirement labels

**Documented** means a capability appears in the supplied specification or FigJam. **Proposed** means a new design decision in this document, not a previously approved requirement. **Fixture** means illustrative data used to test a rule, not a training prescription. **Open** identifies a decision that needs approval before the relevant feature ships. All detailed schemas, rules, and acceptance criteria below are proposed unless explicitly marked documented.

### 1.2 Scope by phase

| Phase | Documented capability | Treatment in this specification |
| --- | --- | --- |
| P1 | Plans, exercise library, manual reps/load, effort confirmation, rest, progression, local history | Define functional behavior and data contracts now. |
| P2 | Supported camera tracking, reps, tempo, range, confidence checks, manual fallback | Reserve an observation interface. Do not require a camera for P1. |
| P3 | Personal recovery trends, combined signals, explained and accepted adjustments | Reserve a recovery interface. No wearable-derived programming in P1. |
| P4 | Meals, saved recipes, estimated macros, correction history | Reserve nutrition references. No nutrition-derived programming in P1. |
| R | Lumbar forces, inverse dynamics, calibrated food geometry, independent validation | Keep outside the production decision path. |

Source: FigJam phase sections 5:503, 5:516, 5:529, 5:542, and 5:555. [S2]

### 1.3 Differences between the two existing sources

The original concept describes automatic HRV-based changes, exact biomechanical/food estimates, and a highly local execution architecture. The board instead places combined recovery signals behind explanation and user acceptance, and places lumbar forces and food geometry in research. These are materially different specifications; neither proves that the technical claims have been achieved. [S1: sections 2-3; S2: 3:272-3:299, 5:555]

**Proposed baseline:** use the board's phase boundaries for this P1 specification, retain the original technical ambitions in R, and record any promotion to a released capability as a separate approved decision. Do not silently carry the concept's 15% HRV rule or exact-force claims into implementation.

### 1.4 Working pilot assumption

Design the initial rules for adults undertaking self-directed resistance training, using a small, reviewed exercise library and reviewed strength/hypertrophy templates. This is a proposed pilot segment, not an established target market. Rehabilitation, clinical treatment, pregnancy/postpartum programming, youth training, and sport-specific performance programming are outside this draft's template coverage. Out-of-scope needs must not receive a fabricated personalized program.

P1 must work without wearable access, camera access, nutrition records, or cloud-generated coaching. The product hypothesis is that useful progression and adaptation can exist before perception is added; the pilot must test that hypothesis.

## 2. Product principles and ownership

**Recorded facts stay separate from estimates.** A user-confirmed log is authoritative as the user's record, not proof that the movement was measured accurately. An inference must retain its source, limitations, and confirmation status.

**Plans stay separate from performance.** Intended sets are not completed sets. A skipped exercise is not zero strength. An interrupted workout is not automatically a failed workout.

**Unknown stays unknown.** Missing effort, body weight, camera measurements, and recovery data must not be filled with a favorable default.

**Consistency comes before novelty.** The engine should preserve the program's intent rather than invent a new routine on every visit. Changes must have a reason and a scope.

**User control is explicit.** P1 generates proposals. Accepting a workout preview applies the displayed changes; chat text alone cannot silently rewrite the plan. A user can pause, end, decline, or manually edit, while the app can withhold unsupported recommendations.

**One governed decision path.** The same rules validate changes requested through a button, chat, or a future sensor. Preference learning cannot override constraints or permission boundaries.

Product owns scope and user-facing behavior. A qualified training-domain reviewer owns exercise content, template prescriptions, progression parameters, and coaching wording. Engineering owns implementation and reproducibility. QA owns executable acceptance cases. Privacy/security review owns data handling and consent design. Named owners remain open.

## 3. Athlete State: the information model

Athlete State is a **versioned view assembled from domain records**, not a single mutable profile blob and not a free-form chat memory. It provides the information needed for a decision without repeatedly loading the entire training history.

### 3.1 Four distinct layers

| Layer | Examples | Write authority |
| --- | --- | --- |
| Reported or observed records | Goal, equipment, completed set, soreness response; later camera output | User action or identified observation source, with provenance. |
| Derived summaries | Last comparable performance, completed weekly sets, progression eligibility | Versioned calculation from identified source records. |
| Plans and recommendations | Next workout, load proposal, curated substitution | Training Brain under the active policy version. |
| Confirmed preferences | Avoid this exercise; use shorter explanations | Explicit user setting, or a learned suggestion the user confirms. |

A model-generated statement such as "you are fatigued" cannot be stored as an observed condition. A rejected load increase cannot be stored as a performed set. Deleting an underlying record invalidates dependent summaries.

### 3.2 Shared record contract

Domain records need `id`, `athlete_id`, `schema_version`, `revision`, `created_at`, and `updated_at`. Records describing events also need `occurred_at`, the user's local date/time-zone context, and a source. Client-created changes carry a stable `operation_id` so a sync retry cannot create a second set.

An observation additionally stores `source_type`, `source_record_id`, `reported_or_measured`, `value`, `unit` where relevant, `confirmation_status`, and `validity_status`. Use statuses such as `usable`, `unconfirmed`, `missing`, `stale`, `conflicted`, or `unassessed`; zero is a value, not a missing-data marker.

Do not attach invented confidence percentages to manual entries or rule outputs. Later perception records can carry task-specific confidence only with a defined interpretation and validation method. Until then, "unassessed" is a complete and valid result.

### 3.3 Minimum onboarding state

| State group | Minimum P1 fields | Collection and use |
| --- | --- | --- |
| Profile | Local athlete ID, adult-eligibility response, time zone, units | Do not require date of birth, sex, height, or weight merely to create a basic program. |
| Goal | Primary goal, effective date, priority | Select a supported template family. Do not invent an outcome deadline. |
| Experience | Self-reported experience; familiar/unfamiliar exercises | Restrict suggestions to the reviewed library's supported skill coverage. |
| Schedule | Available days, usual session duration, scheduling preference | Select a feasible template and place its session sequence. |
| Equipment | Training location, equipment types, known load options/increments | Filter exercises and ensure proposed loads exist. Unknown increments block automatic load-step selection. |
| Constraints | Exercise exclusions, current reported concerns, user-stated restrictions | Filter recommendations; preserve source and scope without making diagnoses. |
| Preferences | Explicit exercise likes/dislikes and coaching style | Rank eligible options, never bypass exclusions. |

Provide an explicit "not sure" response where the user cannot supply an answer. Missing fields required for template eligibility keep the plan in `needs_input`; optional fields do not block onboarding. Body weight may later be needed for a specific supported calculation, but absence must not stop ordinary external-load logging.

### 3.4 Constraint and check-in records

A `Constraint` contains `constraint_id`, `scope` (exercise, movement, body region, or program), `reported_reason`, `source`, `effective_from`, `status`, and any user-confirmed end date. Distinguish a hard exclusion from a preference and distinguish permanent equipment inventory from equipment unavailable today. Persistent exclusions do not disappear because the app has not heard about them recently.

A `DailyCheckIn` contains `checkin_id`, `session_id`, `energy`, `soreness_by_region`, `pain_reported`, `available_minutes`, `equipment_unavailable_today`, `user_requested_adjustment`, and `occurred_at`. Energy and soreness can use labeled choices with an explicit unknown option. Pain is a separate response, not a high value on the soreness scale.

A check-in is scoped to the intended session. Reusing it for a later session requires confirmation. P1 does not calculate a medical readiness score from these answers and does not infer normal recovery from no response.

### 3.5 Program and prescription records

`ProgramVersion` stores `program_id`, `version`, `goal_id`, `template_id`, `template_version`, `policy_version`, `session_sequence`, `schedule`, `effective_from`, `status`, and `accepted_at`. There is only one active version for a given program. Future changes create another version; they never rewrite the program attached to completed workouts.

`SessionPlanRevision` stores the intended date, sequence position, estimated duration, ordered exercise slots, revision, acceptance, and the program version. Each `ExercisePrescription` stores an exercise variant, equipment context, warm-up content reference, working-set targets, rep range, optional effort target, rest prescription, progression policy, and required/optional slot priority.

Preserve the original prescription and any accepted revision. Record which revision applied to each performed set. A user doing something different creates an actual-performance record, not a retroactive edit to what was prescribed.

### 3.6 Workout and set records

`SessionExecution` stores `session_id`, the accepted plan revision, start/end times, status, completion reason, and any unresolved edits. Proposed lifecycle: `planned -> in_progress -> paused -> in_progress -> completed or ended_early`; an unstarted session can become `skipped`. A terminal session is not reopened by an automatic sync merge; later edits are explicit corrections.

`SetLog` contains `set_id`, `session_id`, `prescription_id`, `exercise_variant_id`, `equipment_context_id`, `set_index`, `set_type`, `load`, `load_unit`, `load_basis`, `reps`, `effort`, `status`, `stop_reason`, `occurred_at`, `source`, and revision metadata.

Working, warm-up, and optional extra sets are distinct. Attempted sets with zero completed reps are valid records and are not missing sets. Omitted sets carry a reason when known: time, equipment, user choice, pain, interruption, or unspecified. Effort may be RIR (the user's estimate of additional possible reps), a labeled self-report, or unknown; do not convert between scales without an approved mapping.

**Load semantics are mandatory.** Store whether a number means total barbell load, per-dumbbell load, external bodyweight load, assistance, or a machine setting. Preserve the equipment identity and original unit. A displayed unit conversion must not change the underlying performance or generate a new personal record. An unknown load is not an unloaded exercise.

For bilateral dumbbell movements, the input must say whether the value is per hand. Assisted exercises and arbitrary machine settings do not use ordinary external-load progression unless a matching policy exists. Left/right results need separate records when the approved exercise definition calls for them.

### 3.7 Derived performance state

An `ExercisePerformanceSummary` is keyed by a **comparison context**: exercise variant, equipment context, load convention, rep-counting convention, and prescribed protocol. Store `source_set_ids`, `calculation_version`, `as_of`, `last_comparable_session`, `last_working_load`, `completed_reps`, `qualifying_exposure_count`, `below_target_exposure_count`, and `eligibility_status`.

Do not infer an equivalent working weight when switching machines, changing from barbell to dumbbells, or changing assistance conventions. Preserve each history separately. Reconcile an incorrectly labeled record before using it for progression.

Program-level summaries include prescribed versus completed working sets, session adherence, substitutions, and explicit reasons for incomplete sessions. These are descriptive summaries, not diagnoses of overtraining, muscle recovery, or fitness. No calorie-burn model is part of this contract.

### 3.8 Recommendation and preference records

A `Recommendation` contains `recommendation_id`, `athlete_state_version`, `target_plan_revision`, `action_type`, `before`, `after`, `reason_code`, `evidence_record_ids`, `policy_id`, `policy_version`, `limitations`, `approval_required`, `created_at`, `expires_when`, and `status`.

Proposed lifecycle: `proposed -> accepted or rejected or expired`; an accepted change is applied once in a transaction. `Applied` is recorded only after the plan update succeeds. Changed constraints, corrected evidence, or a new target-plan revision invalidate the proposal and require reevaluation.

Store acceptance and rejection as behavior records, not evidence that an intervention improved health or performance. A reason such as "rack busy today" must not become "dislikes squats." Learned preferences remain suggestions until explicitly confirmed, and users must be able to inspect or remove them.

## 4. State updates, corrections, and persistence

### 4.1 The normal update loop

When the user records a set, validate the unit/load convention and session association, persist the set locally, update only affected summaries, and evaluate whether a new proposal is needed. The UI confirms a save after durable local persistence, not merely after an optimistic display change.

When the user finishes a session, preserve its accepted prescription, mark completed and omitted work accurately, recompute eligible performance summaries, and generate the next-session preview. Session completion does not itself imply that every exercise qualifies for progression.

### 4.2 Corrections and invalidation

A correction retains an audit relationship to the prior revision during normal record retention. Recompute affected summaries and expire unapplied recommendations derived from the old value. Do not rewrite an already performed later workout; its historical decision can remain linked to the state available at that time, with a correction annotation.

**Example:** a user corrects 12 logged reps to 8 after a load increase was proposed. The pending increase is invalidated and the preview is recomputed. The app does not quietly keep the increase or claim that the corrected performance still qualified.

### 4.3 Offline and sync contract

P1 stores the active program, reviewed exercise content, rule configuration, current session, logs, and text explanations locally. Core plan selection, manual logging, deterministic progression, and curated swaps must not depend on a live language-model request. This implements the source's local-first direction without asserting that every future capability is offline. [S1: section 3; S2: 1:61, 1:66, 2:172]

Sync uses stable record IDs and operation IDs, with revision checks. Merge independent additions; do not use silent last-write-wins for conflicting edits to the same set or active prescription. Flag the conflict and withhold dependent increases until the user resolves it. An active workout is pinned to its accepted revision; background sync cannot replace it mid-set.

In a first release, limiting live workout execution to one device at a time is a proposed simplification. Offline sessions independently created on two devices remain separate records for review rather than being guessed into one workout.

### 4.4 Privacy and deletion

Collect only the fields used by the enabled feature. Camera, wearable connection, optional cloud processing, backup, and research/model-training use need distinct purpose controls rather than one blanket setting. Do not reuse workout or camera data for training models merely because the user used the app.

Apply access controls, encryption appropriate to storage/transit, and explicit export/deletion behavior. Product analytics should not contain raw health narratives, chat text, or video. Backups must respect deletion and must not silently resurrect removed records. Auditability does not mean indefinite retention; retention periods, backup expiry, provider access, and deletion verification require privacy/security approval before launch.

## 5. Training Brain: decision contract

### 5.1 Inputs and outputs

The input is a versioned Athlete State snapshot, a triggering event, the applicable program/plan revision, an approved exercise/template library, and a versioned policy bundle. Later perception or recovery signals enter only through their defined interfaces.

The output is one of: `keep_plan`, `propose_change`, `needs_input`, `unassessed`, or `withhold_guidance`. It includes a reason code, referenced evidence, before/after values when applicable, and user-facing wording. A no-change decision is a first-class output, not an error.

**Proposed pipeline:** read current state; check scope, permissions, and constraints; assess data validity; generate eligible candidates; apply policy bounds; select deterministically; produce a proposal; validate the proposal again when the user accepts it.

### 5.2 Priority order

| Priority | Rule category | Effect |
| --- | --- | --- |
| 1 | User stop, reported pain, hard exclusions, unsupported scope | Withhold conflicting guidance; never overcome these by personalization. |
| 2 | Data validity and current plan revision | Request missing data or hold changes when evidence is incomplete, stale, or conflicted. |
| 3 | Equipment, session time, and approved template constraints | Remove infeasible candidates. |
| 4 | Current program intent and comparable performance | Determine whether to repeat, progress, or propose a reviewed alternative. |
| 5 | Explicit preferences, then confirmed learned preferences | Rank remaining eligible candidates. |
| 6 | Explanation style | Change wording, not the underlying prescription. |

A constraint at a higher priority cannot be bypassed by a lower-priority reason. When rules conflict, return the higher-priority outcome and record the suppressed candidate for debugging, not as a second suggestion to the user.

### 5.3 Language-model boundary

A language model may interpret a request into an allowlisted intent, summarize confirmed records, and explain a validated recommendation. It may not independently create exercises, decide unreviewed loads, invent missing history, diagnose pain, estimate internal joint forces, or write directly to authoritative state.

Supported P1 intents are `explain_plan`, `shorten_session`, `request_substitution`, `change_availability`, `log_performance`, and `report_concern`. Ambiguous writes require a preview or confirmation. Notes and chat content are data, not instructions that can override the rule bundle. Every write uses the same validation path as the structured interface.

Cloud chat is an optional proposed enhancement, not a requirement inherited from the source. Without a connection, the structured interface and deterministic explanations remain available; unavailable generative chat must not pretend to have completed a change.

## 6. P1 training policies

### TB-01. Initial program selection

Select from reviewed, versioned templates that match the supported goal, experience coverage, available equipment, days, and time budget. Each template explicitly defines session order, exercise roles, eligible substitutions, working-set prescriptions, effort/rest instructions, and progression rules.

Filter hard exclusions first. Rank eligible templates by the declared goal, schedule fit, familiar exercise coverage, and explicit preference, then use a stable template ID as the final tie-breaker. If no reviewed template fits, return `needs_input` or an unsupported-scope message rather than constructing an unreviewed routine.

The first plan displays its rationale and is activated by the user. A starting load comes from comparable user-confirmed history or a user-led familiarization flow defined by the reviewed template. Do not guess strength from age, body weight, sex, or an unrelated exercise. No maximum-effort testing is required by this product specification.

### TB-02. Session order and missed workouts

Maintain a program session sequence separately from calendar dates. Missing Tuesday does not erase Tuesday's intended session, automatically double Thursday's work, or reset the whole program.

When a session is skipped, propose the next feasible placement using the template's scheduling constraints. The user chooses whether to move it or skip forward. Work omitted because of time is not automatically added to the next session. A paused workout offers resume or end; it must not be duplicated when the app restarts.

### TB-03. Time-limited workouts

Use each template's required/optional exercise roles and reviewed duration assumptions. Remove optional work first, then select an approved shorter variant when available. Preserve the template's warm-up and rest constraints; do not silently compress rest to fit the countdown.

Show what was removed, the revised estimated duration, and what remains unchanged. If required work cannot fit, offer a reviewed short session or rescheduling rather than a fabricated compressed plan. A time-limited revision is tagged so it does not create a false signal of declining performance.

### TB-04. Load and rep progression

Use exercise-specific, reviewed progression policies rather than a universal "increase weight" rule. A simple candidate for P1 is double progression: work within a prescribed rep range, then propose a load increase when the configured conditions are met. This is a proposed software policy, not a validated prescription for every user.

A load-increase candidate requires all designated working sets to be complete in a comparable, unmodified exposure; the configured rep criterion to be met; any required effort reports to be present and eligible; the configured number of qualifying exposures to be reached; no blocking concern or exclusion; and an available equipment step inside the policy's permitted bound. Missing effort does not count as passing an effort criterion.

Each policy must define a usable-history horizon and the maximum gap between qualifying exposures. Older evidence requires baseline reconfirmation rather than an automatic increase. In a consecutive-exposure policy, a comparable exposure that fails the criterion resets the streak; a modified or conflicted exposure cannot silently bridge it.

Propose only the next supported load step. After a load change, reset the next rep target according to the template and reset the qualifying-exposure counter. Do not simultaneously add working sets unless an explicitly reviewed combined policy allows it. If the next available increment exceeds the allowed bound, keep the load and use an approved rep/hold option; never round upward past the bound.

When performance is within the prescribed range but below its ceiling, repeat the load and propose the next rep target only according to the template's rep-allocation rule. When comparable performance is below target, hold automatic increases and capture context. A reviewed repeat-underperformance trigger may create a program-review suggestion, but it must not diagnose fatigue or automatically deload the user.

### TB-05. Intra-session behavior

Keep the accepted target visible while a set is underway. P1 does not raise a target mid-repetition or interrupt a set with a newly generated program change. After the set, accept actual reps/load/effort and show any next-set proposal during rest.

Automatic escalation based on one apparently easy set is disabled in this draft. Users can request a change; it goes through the reviewed policy and an explicit preview. Persist every accepted change against the sets it affects. An extra set performed by the user is logged as extra, not retroactively counted as prescribed work.

### TB-06. Curated exercise substitutions

The board explicitly calls for curated exercise swaps. [S2: 2:124] Implement reviewed, directional substitution relationships attached to an exercise role, not a language-model assertion that two exercises train similar muscles.

Filter candidates by hard exclusions, equipment available today, supported skill coverage, and the slot's reviewed substitution list. Rank eligible candidates by role fit, familiarity, explicit preference, then library order. Explain the relevant tradeoff. If no eligible substitute exists, offer skipping or rescheduling the slot rather than inventing an equivalent movement.

Use the substitute's own history and loading convention. A machine press never inherits a barbell's working weight just because it occupies the same slot. A temporary equipment substitution does not permanently alter the user's exercise preference or original exercise baseline.

### TB-07. Energy, soreness, and requests for a lighter session

P1 uses the user's current check-in as context, not as a medical readiness measurement. A low-energy or soreness report may prompt the user to choose a reviewed lighter option, keep the plan, or end/reschedule. Do not silently down-regulate training because a score crosses an invented threshold.

A lighter option must identify the exact changed variable and use the template's bounds. Combining multiple signals must not accidentally stack several reductions or increases. Persistent goal/schedule changes require a program-level preview rather than repeated session-level patches.

Wearable readings, sleep-stage rules, and weather-derived modifications remain P3 or R as shown in the board. They do not affect this P1 policy. [S2: 3:254-3:305]

### TB-08. Reported pain and unsupported concerns

Treat a report of pain as separate from ordinary soreness. Suppress progression and automated exercise-replacement advice for the affected activity, show a stop/pause option, and use approved wording that does not diagnose or encourage training through pain. Continuing elsewhere in the app does not constitute clearance to resume the affected movement.

Store only the user-reported concern and its scope. Do not claim that a different exercise is safe for the reported condition. Clinical escalation wording, emergency messaging, and the process for removing a persistent restriction need qualified review before release. This rule is a conservative product guardrail, not a clinical triage protocol.

### TB-09. Preference learning

An explicit choice has priority over an inferred pattern. Save why a recommendation was declined when the user chooses to provide a reason. Repeated behavior may trigger a question such as "Make this your usual alternative?" but cannot silently become a permanent preference.

A preference is scoped: one session, one location, one exercise role, or the entire program. Users can inspect and reset it. Do not optimize solely for acceptance; easy-to-accept recommendations may not serve the user's stated goal. Outcome claims require a separate evaluation design.

### TB-10. Program review and goal changes

A new primary goal, sustained availability change, or repeated policy-defined underperformance can create a review proposal. Show how the proposed program differs and which history remains relevant. Activate only after user confirmation.

Do not infer a need for extra muscle-group volume from one isolated personal record. Do not claim a plateau without enough comparable observations under a defined policy. Keep historical program versions available, and do not schedule automatic model-driven experimentation on the user in P1.

## 7. Minimum exercise-library contract

The Training Brain cannot operate on exercise names alone. The following is the minimum dependency for P1; a separate Exercise Ontology document can expand it without changing this contract.

| Field group | Required content |
| --- | --- |
| Identity | Stable exercise and variant IDs; display name; library version; review status. |
| Role | Reviewed movement/slot roles and training-intent tags used by templates. |
| Equipment | Required equipment, equipment-context rules, loading convention, supported increments. |
| Execution | Reviewed instructions, rep-count convention, bilateral/unilateral handling, warm-up content reference. |
| Eligibility | Supported experience coverage and exclusion tags; no automated diagnosis matching. |
| Substitution | Directional approved alternatives, applicable slot, tradeoff note, candidate order. |
| Progression | Policy ID and version, supported prescription type, required evidence fields. |
| Future camera support | Separate per-metric support status; no automatic camera eligibility from exercise-library inclusion. |

Only reviewed, enabled entries are eligible for generated programs. Imported or user-created exercises can be logged without receiving automated progression or technique guidance until the necessary metadata and policy exist. Disabling an exercise prevents new recommendations but preserves historical records and the content version used previously.

## 8. Decision examples and test fixtures

**All numbers and people in this section are fixtures.** They exercise the product logic; they are not recommended prescriptions, benchmark results, or records about the user.

### 8.1 A qualifying load increase

Fixture policy `DP_TEST_01`: three designated working sets; rep range 8-10; minimum reported RIR 2 on each set; two consecutive qualifying comparable exposures; available total-load increment 5 lb; maximum permitted load change 5%; reset target 8 reps per set. For this fixture, both exposures and the proposed next session fall within the policy's configured history and gap limits. The policy's numeric values require training-domain approval before any real use.

| Evidence | Exposure A | Exposure B |
| --- | --- | --- |
| Exercise context | Same barbell bench-press variant | Same variant and equipment context |
| Total load | 100 lb | 100 lb |
| Completed reps | 10 / 10 / 10 | 10 / 10 / 10 |
| Reported RIR | 2 / 2 / 2 | 2 / 2 / 2 |
| Prescription altered? | No | No |
| Blocking concern? | No | No |

Expected output: propose 105 lb with an 8-rep target for each of three sets. The 5 lb step is 5% of 100 lb, matches available equipment, and is within this fixture's bound. Preserve the current plan until acceptance. Do not also add a set. Reset the qualifying counter only when the accepted load change takes effect.

User-facing explanation: "You completed the top of this rep range in both qualifying sessions and reported the required effort margin. The next available step is 105 lb. Review the increase before your next session."

### 8.2 Progress, but not yet a load increase

Use the same fixture rep range. The latest comparable exposure is 100 lb for 9 / 8 / 8 with eligible effort reports. Under a fixture rule that adds one total target rep to the first set below the ceiling, the next proposal is 100 lb for 10 / 8 / 8. The working-set count stays three.

A result of 8 / 8 / 8 does not meet a 10-rep ceiling. Eligibility is evaluated against the configured range, not merely completion of the previous target. Unknown effort produces `needs_input` or a hold, not an invented RIR. A separate rep-only policy could be added after review, but is not implicitly enabled here.

### 8.3 Less time and unavailable equipment

Fictional user Alex has an accepted upper-body session estimated at 60 minutes and now reports 35 minutes with the rack unavailable. The engine first applies constraints, then searches reviewed substitutes and a shorter template variant. It does not redesign the full training week.

Fixture result: keep the required pulling slot, replace the unavailable pressing slot with an eligible reviewed machine alternative, and omit two optional accessory slots. The revised plan is proposed only if the template's duration model fits the time budget. Because Alex has no comparable machine history, that exercise enters the reviewed familiarization flow; it does not inherit the barbell load.

The resulting logs preserve that this was a shortened session. Completing its revised target does not count as a full, unmodified exposure toward the original barbell progression rule.

### 8.4 Corrected data, declined advice, and pain

If Alex corrects Exposure B from 10 / 10 / 10 to 10 / 10 / 8 before accepting the increase, the increase expires. If Alex declines a valid increase because heavier plates are unavailable, log the reason as a temporary equipment issue. If Alex reports pain on the relevant movement, suppress the increase and route to the approved concern flow even when every progression criterion otherwise passes.

These three cases must produce different reason codes. They must not all be labeled "not ready."

### 8.5 Illustrative recommendation payload

This is a readable example of the decision contract, not a full API schema. Its IDs refer to the fixtures above.

```json
{
  "recommendation_id": "rec_test_001",
  "athlete_state_version": 42, "target_plan_revision": 7,
  "action_type": "propose_load_increase",
  "exercise_context_id": "bench_barbell_total_lb",
  "before": {"load": 100, "unit": "lb", "sets": 3},
  "after": {"load": 105, "unit": "lb", "sets": 3,
            "target_reps": [8, 8, 8]},
  "reason_code": "QUALIFYING_EXPOSURES_COMPLETE",
  "evidence_record_ids": ["exposure_A", "exposure_B"],
  "policy_id": "DP_TEST_01", "policy_version": "fixture_1",
  "limitations": ["effort_is_self_reported"],
  "approval_required": true,
  "expires_when": ["evidence_changes", "constraints_change",
                   "target_plan_revision_changes"],
  "status": "proposed"
}
```

Acceptance is not a blind replay of this payload. Re-read the relevant state, verify scope/revisions and bounds, and atomically apply the change once. A repeated acceptance request returns the already applied result rather than applying another 5 lb increase.

## 9. User experience contract

| Surface | What the user sees or does | State/decision requirement |
| --- | --- | --- |
| Onboarding | Goal, experience, schedule, equipment, exclusions | Collect minimum required state; optional fields can remain unknown. |
| Today | Accepted workout and any proposed changes | Display the current plan revision and a concise reason for each change. |
| Before workout | Time, availability, energy/soreness, concern response | Scope check-in to this session; never imply wearable data exists. |
| Set logging | Actual load, reps, optional effort, stop reason | Make total/per-hand/assistance conventions explicit; save locally. |
| Ask Trainer | Explain, shorten, swap, or change availability | Convert requests to validated intents and show write previews. |
| Session summary | Completed, skipped, and extra work; next proposal | Separate outcomes from interpretations and original from revised targets. |
| History/settings | Performance context, preferences, corrections, export/delete | Keep provenance visible where it affects trust or future decisions. |

Every recommendation needs a compact "Why?" view showing the decisive records, the rule applied, and material missing data. The main screen can remain brief; transparency belongs one tap away rather than in a wall of coaching text.

Examples of appropriate wording: "Keep the same load; one prescribed set is not logged" or "No load recommendation yet for this machine." Avoid unsupported conclusions such as "Your CNS is fatigued," "your spine is safe," or "this exercise will prevent injury."

## 10. Interfaces for later phases

### 10.1 P2: perception observations

The documented board path includes tracking reliability, marking an exercise unassessed, and manual confirmation. [S2: 2:151-2:163] A future `PerceptionObservation` links a metric, unit, exercise context, source window, model version, capture conditions, validity state, and any validated confidence interpretation to the relevant set.

Camera observations remain separate from user-confirmed logs. P2 may prefill reps for confirmation. It must not overwrite an explicit correction, infer effort solely from rep count, or treat a missing technique assessment as good technique. Promotion of an observation to progression evidence requires a per-metric validation decision.

### 10.2 P3: recovery observations

A future `RecoveryObservation` includes metric type, value/unit, measurement method, device/source, time window, validity, and baseline reference. Data sufficiency and personal baselines are documented concepts in the board; their numerical algorithms are not specified there. [S2: 3:257-3:272]

Reserve these fields without supplying a production HRV threshold, sleep-stage rule, or readiness score. A future recovery policy proposes bounded changes through the same acceptance and audit path. New overnight information does not silently rewrite a session already underway.

### 10.3 P4 and R boundaries

Nutrition can later provide user-confirmed meal estimates and trends, with their own provenance and correction history. Whether and how those records change training remains a separate proposed decision; the current meal flow does not establish such an algorithm. [S2: 4:406-4:421]

Research outputs, including inverse dynamics and food geometry, cannot write into released Athlete State summaries as validated measurements merely because a research job returned a number. Any promotion requires defined supported conditions, independent evaluation, claims review, and versioned release approval. [S2: 5:555]

## 11. Acceptance criteria

These are proposed behavioral tests for the P1 implementation. Passing them establishes conformance to the specification, not clinical effectiveness or universal training safety.

### 11.1 Athlete State and persistence

| ID | Given / when | Expected result |
| --- | --- | --- |
| AS-01 | An optional body-weight or effort field is missing | Store unknown; do not write zero or fabricate a value. |
| AS-02 | The user switches displayed units | Preserve the same performance and context; do not create a new record or load increase. |
| AS-03 | A completed-set save is retried after reconnecting | One logical set exists, keyed by the same operation ID. |
| AS-04 | A completed set is corrected | Recompute dependent summaries and expire pending dependent recommendations. |
| AS-05 | A workout is interrupted and the app reopens | Restore the last durable session state; offer resume or end. |
| AS-06 | Two devices edit the same set differently | Surface a conflict; do not silently pick the value that permits progression. |
| AS-07 | A future program is changed | Preserve completed sessions and their original program/prescription versions. |
| AS-08 | The user deletes a record or account | Remove or invalidate dependent data per the approved deletion policy; backup restore cannot resurrect it. |

### 11.2 Training decisions

| ID | Given / when | Expected result |
| --- | --- | --- |
| TB-11 | No reviewed template matches required constraints | Return needs-input/unsupported scope, not an invented routine. |
| TB-12 | Both qualifying fixture exposures meet every condition | Propose 105 lb and 3 x 8; await acceptance. |
| TB-13 | Reps meet the fixture ceiling but required RIR is unknown | Do not qualify that exposure for the effort-dependent load rule. |
| TB-14 | The next available increment exceeds the permitted bound | Hold load or use an approved rep option; never round beyond the bound. |
| TB-15 | A substitute uses a different machine or load convention | Retrieve its own baseline or familiarization flow. |
| TB-16 | A session was shortened or sets omitted for time | Do not treat omission as strength failure or a full original qualifying exposure. |
| TB-17 | A workout is missed | Offer reschedule/skip; do not automatically double the next workload. |
| TB-18 | A user reports relevant pain despite qualifying performance | Suppress progression and use the approved concern flow. |
| TB-19 | Relevant evidence changes before acceptance | Reject stale application and generate a new preview. |
| TB-20 | The acceptance request is delivered twice | Apply the accepted revision once, not twice. |

### 11.3 Boundaries and explanations

| ID | Given / when | Expected result |
| --- | --- | --- |
| AI-01 | Chat requests an exercise outside the eligible library | No direct write; return an eligible option or explain unsupported scope. |
| AI-02 | Cloud chat is unavailable | Local manual training and deterministic decisions continue; unavailable chat is labeled accurately. |
| AI-03 | A recommendation is rejected for equipment unavailable today | Do not create a permanent dislike or exclusion. |
| AI-04 | A higher-priority exclusion conflicts with a preference | Exclusion wins; explanation identifies the constraint without diagnosis. |
| AI-05 | Camera or wearable data is absent | P1 remains usable; do not claim the user was observed or recovered. |
| AI-06 | A background update arrives during a set | Keep the active prescription unchanged until an appropriate reviewed transition. |
| AI-07 | The same state, event, and rule/library versions are replayed | Produce the same action and reason code; wording may vary only without changing meaning. |
| AI-08 | Research returns a joint-force estimate | It remains research data and cannot trigger a released safety or progression decision. |

## 12. Pilot measurement and release gates

### 12.1 Define what will be measured

**Activation:** a user accepts an initial plan, records at least one completed working set, and ends that first session. Report full completion and early ending separately; do not label both as full completion.

**Repeat use:** among an activated cohort, the share that completes a subsequent workout within the next 14 days, plus the share that completes at least one workout during days 22-28 after activation. These are proposed reporting windows, not success benchmarks.

**Plan adherence:** completed prescribed working sets divided by prescribed working sets in the applicable accepted session revisions. Also report change from the original prescriptions so shortening workouts cannot invisibly inflate adherence. A zero-set denominator is not applicable.

**Recommendation behavior:** shown, accepted, rejected, expired, and applied counts by action and reason. Report acceptance per shown proposal and actual application per accepted proposal separately. Do not interpret acceptance as proof of improved outcomes.

**Reliability and trust:** lost-save incidents, duplicate-set incidents, sync conflicts, stale-proposal attempts, corrected entries, unknown-effort frequency, and user-reported confusing recommendations. Measure latency on the selected P0 device floor; no latency number here is a proven capability.

### 12.2 Minimum event contract

Events need an event ID, occurrence time, pseudonymous actor, session/recommendation IDs when applicable, app version, policy/library versions, and relevant state revision. Instrument `plan_accepted`, `session_started`, `set_saved`, `set_corrected`, `session_ended`, `recommendation_shown`, `recommendation_accepted`, `recommendation_rejected`, `recommendation_applied`, `recommendation_expired`, `sync_conflict`, and `guidance_withheld`.

Use controlled reason codes rather than copying raw health or chat narratives into analytics. Define deduplication and session-status semantics before comparing cohorts.

### 12.3 Release gates

Every applicable acceptance test must pass on the supported implementation. Require approved template/exercise content, reproducible decisions, successful local save/resume and conflict tests, verified deletion behavior, and reviewed concern-flow copy. No critical known defect that loses logs, bypasses constraints, or applies an unaccepted change can remain open.

P1's documented product gate is whether users repeat complete workouts. [S2: 5:500] Numeric retention, completion, and usability targets remain open until the pilot segment and baseline are defined. Do not use arbitrary camera accuracy or consumer-retention percentages as inherited requirements.

## 13. Implementation work packages

| Package | Concrete output | Dependency / completion evidence |
| --- | --- | --- |
| A. Domain records | Profile/context, constraints, plans, sessions, set logs, revisions, recommendation records | Schema validation and AS-01 through AS-08. |
| B. Reviewed content | Initial exercise library, templates, substitutions, progression policy bundles | Named training reviewer and approved coverage manifest. |
| C. Local decision engine | Deterministic filters, policy evaluation, reason codes, pending proposals | Replay tests and TB-11 through TB-20. |
| D. User workflow | Onboarding, Today, check-in, manual workout, summary, acceptance/correction controls | Complete end-to-end offline workout and revision tests. |
| E. Sync and privacy | Deduplicated backup/sync, conflict handling, access controls, export/deletion | Recovery, conflict, and deletion demonstrations. |
| F. Pilot instrumentation | Event definitions, cohort queries, reliability dashboard, feedback capture | Auditable metric calculations before interpreting results. |

Build a thin end-to-end slice through A-D first: one reviewed program, one workout, real manual logs, one explained next-session proposal, and an accepted update. Add broader content and edge cases before expanding to P2. These are work-package recommendations, not created tickets or assigned commitments.

## 14. Decisions required before release

| Decision | Proposed position in this draft | Approval needed |
| --- | --- | --- |
| Pilot audience and goal coverage | Adults doing self-directed resistance training; limited strength/hypertrophy templates | Product and training-domain reviewer. |
| Initial exercise/template set | Small reviewed library; no invented coverage count | Product and training-domain reviewer. |
| Prescription parameters | Exercise-specific rep/set/effort/rest and progression bundles | Training-domain reviewer; fixtures are not defaults. |
| Missing-effort policy | Hold effort-dependent increases; support manual choice | Product and training-domain reviewer. |
| Change approval | Preview and explicit acceptance for P1 prescription changes | Product/design. |
| Account and sync scope | Local identity; consider one active workout device | Product/engineering/privacy. |
| Concern handling | Separate pain from soreness; withhold conflicting guidance | Qualified safety review and product. |
| Data retention and model use | Purpose-specific controls; no implied research consent | Privacy/security review. |
| Source precedence | Board phase boundaries for P1; original ambitions retained in R | Product owner. |
| Pilot success thresholds | Define after segment and baseline, before go/no-go evaluation | Product/analytics. |

Schemas and test prototypes can proceed against this proposal. Production training policies, supported-user claims, and release approval must wait for the relevant decisions and reviewed content. This document does not establish that the original biomechanical, food-volume, or adaptive-recovery claims have been validated.

## 15. Source register and traceability

**[S1] Product Specification: Edge-Compute AI Personal Trainer.** Supplied file: `product_specification_ai_trainer.md`. Section 1 establishes the telemetry-led concept; sections 2.1-2.2 describe biomechanical and food-geometry ambitions; section 2.3 describes wearable/environmental scheduling; section 3 specifies local-first architecture; section 4 gives the intended daily journey. These are source statements, not verification of feasibility or measured performance.

**[S2] AI Trainer - Complete App and Development Phases.** FigJam board supplied by the user and read on September 17, 2026. File key: `tMrXrvbsPVsKAQJf8SaI0I`; page `0:1`.

Board: https://www.figma.com/board/tMrXrvbsPVsKAQJf8SaI0I/AI-Trainer--Complete-App-and-Development-Phases?node-id=0-1

Key anchors: `1:9-1:44` core P1 journey; `2:118-2:175` workout/manual/camera branch; `2:124` curated swaps; `2:151-2:163` reliability and confirmation; `3:257-3:299` data sufficiency, combined signals, and accepted adjustment; `5:503` P1; `5:516` P2; `5:529` P3; `5:542` P4; `5:555` research boundary. Ranges identify related node IDs, not an assurance that every intervening numeric ID is a content node.

**Traceability note:** Sources define capabilities and phase boundaries. They do not supply the detailed Athlete State schema, the Training Brain algorithms, clinical criteria, quantitative validation results, or launch thresholds. Those additions are explicitly proposed here, with illustrative numeric values confined to fixtures.
