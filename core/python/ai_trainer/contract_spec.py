"""The single source of truth for every record that crosses the Swift ⇄ Python boundary.

Two generators consume this module:

- ``scripts/generate_schemas.py``      → ``core/python/ai_trainer/{request,response}.schema.json``
- ``scripts/generate_swift_models.py`` → ``apps/ios/Sources/AITrainerCore/Models.swift``

Change a record here, run both generators, commit the outputs. CI diffs them.

Field spec mini-language (one string per model, space-separated ``name:Type`` entries):

- ``Type`` is a primitive (``String Number Int Bool UUID Date``), an enum, or a model name.
- ``[Type]`` is an array; ``{Type}`` is a string-keyed map.
- A trailing ``?`` on the name marks the field optional (absent or ``null``).

Swift-only metadata (defaults, ``Set`` collections, type names) lives in the
``SWIFT_*`` tables below; it never affects the JSON schema.
"""

from __future__ import annotations

# No ``dataclasses`` here: it drags in ``inspect``/``dis``/``_opcode``, which the embedded
# iOS runtime does not ship (see tests/test_embedded_imports.py). Plain classes instead.

# --------------------------------------------------------------------------- #
# Primitives and enums
# --------------------------------------------------------------------------- #

# ``Object`` is an unchecked JSON object: only ``migrateState`` takes one, and validates it after upgrading.
PRIMITIVES: dict[str, str] = {
    "String": "string",
    "Number": "number",
    "Int": "integer",
    "Bool": "boolean",
    "Object": "object",
}

UUID_PATTERN = "^[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}$"
DATE_DESCRIPTION = (
    "Exact binary64 seconds since 2001-01-01T00:00:00Z (Foundation reference epoch). "
    "No Unix-epoch conversion; preserves existing audit timestamps."
)

# Insertion order matters: the schema generator emits ``$defs`` in this order.
ENUMS: dict[str, list[str]] = {
    "Review": ["fixture", "approved", "disabled"],
    "Unit": ["lb", "kg"],
    "Basis": ["total", "perHand", "machineSetting", "assistance", "externalBodyweight"],
    "SessionStatus": ["inProgress", "paused", "completed", "endedEarly", "skipped"],
    "SetKind": ["working", "warmUp", "extra"],
    "Outcome": ["keepPlan", "proposeChange", "needsInput", "unassessed", "withholdGuidance"],
    "RecommendationStatus": ["proposed", "applied", "rejected", "expired"],
    "Omission": ["time", "equipment", "userChoice", "pain", "interruption", "unspecified"],
    "StatusKind": ["onBreak", "sick", "injured"],
    "DietGoal": ["fatLoss", "muscleGain", "maintenance", "endurance"],
    "DietPattern": ["omnivore", "vegetarian", "vegan"],
    "ActivityLevel": ["inactive", "lowActive", "active", "veryActive"],
    "EquationSex": ["female", "male"],
    "TrainingLoad": ["light", "moderate", "high", "veryHigh"],
    "DietStatus": ["ready", "needsInput", "withheld"],
    "AdaptationPace": ["slower", "standard"],
    "ChatTopic": [
        "exerciseProgress",
        "nextSession",
        "week",
        "lessTime",
        "moveOrSkip",
        "pain",
        "away",
        "changePlan",
        "evidence",
        "diet",
        "other",
    ],
    "ChatActionKind": [
        "ask",
        "openToday",
        "openDiet",
        "openLoad",
        "openSwap",
        "openLessTime",
        "openMoveDay",
        "openPain",
        "openStatus",
        "openChangeDays",
        "confirmSkip",
        "requestProgression",
        "requestShorten",
        "requestReplan",
        "reportPain",
        "setStatus",
        "endStatus",
    ],
}

# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #


class FieldSpec:
    """One record field: ``type`` is e.g. ``"String"``, ``"[Slot]"``, ``"{Omission}"``, ``"UUID"``."""

    __slots__ = ("name", "optional", "type")

    def __init__(self, name: str, type: str, optional: bool = False) -> None:
        self.name = name
        self.type = type
        self.optional = optional

    @property
    def is_array(self) -> bool:
        return self.type.startswith("[")

    @property
    def is_map(self) -> bool:
        return self.type.startswith("{")

    @property
    def element_type(self) -> str:
        return self.type[1:-1] if (self.is_array or self.is_map) else self.type


class ModelSpec:
    __slots__ = ("doc", "fields", "name")

    def __init__(self, name: str, fields: tuple[FieldSpec, ...], doc: str = "") -> None:
        self.name = name
        self.fields = fields
        self.doc = doc


def _parse_fields(specification: str) -> tuple[FieldSpec, ...]:
    parsed: list[FieldSpec] = []
    for entry in specification.split():
        raw_name, type_name = entry.split(":")
        optional = raw_name.endswith("?")
        parsed.append(FieldSpec(raw_name.rstrip("?"), type_name, optional))
    return tuple(parsed)


def _model(name: str, specification: str, doc: str = "") -> ModelSpec:
    return ModelSpec(name, _parse_fields(specification), doc)


# Domain records, in ``$defs`` order. ``Omissions`` and ``Request`` are structural
# definitions inserted by the schema generator at the marked positions.
MODELS: list[ModelSpec] = [
    _model(
        "Profile",
        "adultConfirmed:Bool supportedScopeConfirmed:Bool goal:String experience:String daysPerWeek:Int "
        "minutes:Int equipment:[String] preferredUnit:Unit timeZone:String excludedExercises:[String] "
        "preferredExercises:[String] freeDays?:[Int] minutesByDay?:{Int}",
        "What the athlete told us at onboarding. No body metrics, no estimated strength. ``freeDays`` are "
        "weekdays 0-6 (Monday = 0) and ``minutesByDay`` maps a weekday to that day's minutes; both stay "
        "absent until the athlete gives them (ADR-017).",
    ),
    _model(
        "Equipment",
        "id:String name:String kind:String unit:Unit basis:Basis availableLoads:[Number]",
        "One physical piece of equipment as the athlete identifies it. Loads never transfer between identities.",
    ),
    _model(
        "Exercise",
        "id:String name:String role:String equipmentKind:String basis:Basis alternatives:[String] "
        "review:Review contentVersion:String",
        "A governed library exercise. ``alternatives`` are directional curated substitutes.",
    ),
    _model(
        "Policy",
        "id:String version:String review:Review requiredExposures:Int minimumRIR:Int "
        "maximumIncreaseFraction:Number historyDays:Int maximumGapDays:Int",
        "Progression policy parameters. Values are supplied by the content bundle, never assumed.",
    ),
    _model(
        "Library",
        "exercises:[Exercise] policy:Policy permitsFixtures:Bool",
        "The bundled content the core runs against, as the host displays it.",
    ),
    _model(
        "Slot",
        "id:UUID exerciseID:String equipment:Equipment protocolID:String workingSets:Int lowerReps:Int "
        "upperReps:Int targets:[Int] load?:Number restSeconds:Int optional:Bool estimatedMinutes:Int",
        "A prescription for one exercise in a session. ``load`` absent means unknown, never zero.",
    ),
    _model(
        "Plan",
        "id:UUID revision:Int name:String slots:[Slot] modified:Bool scheduledDate?:Date warmUpMinutes:Int "
        "weekday?:Int",
        "One session's accepted prescriptions. ``modified`` marks a temporary shortened/substituted copy. "
        "``weekday`` (0-6, Monday = 0) is the day a weekly plan (ADR-017) puts this session on.",
    ),
    _model(
        "Program",
        "id:UUID revision:Int templateID:String libraryVersion:String plans:[Plan] sequenceIndex:Int acceptedAt:Date",
        "The accepted sequence of session plans; ``sequenceIndex`` points at the next one.",
    ),
    _model(
        "CheckIn",
        "energy?:String soreness?:String painReported:Bool minutes?:Int unavailableEquipment:[String] occurredAt:Date",
        "Subjective pre-session input. Recorded, never scored.",
    ),
    _model(
        "SetLog",
        "id:UUID operationID:UUID revision:Int prescriptionID:UUID contextKey:String index:Int kind:SetKind "
        "load?:Number unit:Unit basis:Basis reps:Int rir?:Int occurredAt:Date conflicted:Bool",
        "What actually happened in one set. ``operationID`` makes saves idempotent.",
    ),
    # -> Omissions (map of slotID:index -> Omission) is inserted here by the schema generator.
    _model(
        "Session",
        "id:UUID programID:UUID programRevision:Int originalPlan:Plan plan:Plan status:SessionStatus "
        "startedAt:Date endedAt?:Date timeZone:String checkIn:CheckIn logs:[SetLog] omissions:Omissions "
        "restEndsAt?:Date",
        "A workout from start to summary. Keeps the original and the accepted plan for provenance.",
    ),
    _model("Evidence", "id:UUID revision:Int", "A set log id/revision a decision relied on."),
    _model(
        "Decision",
        "outcome:Outcome reason:String explanation:String after?:Plan evidence:[Evidence] week?:WeekOption",
        "The Training Brain's answer. ``after`` is the proposed plan for ``proposeChange`` outcomes; ``week`` is "
        "the proposed week for a ``replan`` (ADR-018), built into a program only when accepted.",
    ),
    # -> Request (a tagged union over REQUEST_KINDS) is inserted here by the schema generator.
    _model(
        "Recommendation",
        "id:UUID stateRevision:Int contextRevision:Int targetPlanID:UUID targetPlanRevision:Int "
        "request:Request decision:Decision policyVersion:String createdAt:Date status:RecommendationStatus "
        "rejectionReason?:String",
        "A proposal pinned to the context it was computed against. Inert until accepted.",
    ),
    _model("Audit", "id:UUID previous:SetLog correctedAt:Date", "The set log a correction replaced."),
    _model(
        "Conflict",
        "id:UUID sessionID:UUID current:SetLog incoming:SetLog",
        "Two competing versions of one set. Resolved explicitly by the athlete, never silently.",
    ),
    _model("Event", "id:UUID name:String occurredAt:Date stateRevision:Int reason?:String", "Local analytics event."),
    _model("Nutrients", "calories:Number protein:Number carbs:Number fat:Number"),
    _model(
        "Meal",
        "id:UUID revision:Int name:String nutrients:Nutrients occurredAt:Date source:String timeZone:String",
        "A user-confirmed nutrient estimate for one eaten portion.",
    ),
    _model("MealAudit", "id:UUID previous:Meal correctedAt:Date"),
    _model("Recipe", "id:UUID name:String perServing:Nutrients source:String", "An immutable saved portion."),
    _model(
        "DietScreening",
        "pregnant:Bool lactating:Bool conditions:[String] scoffAnswers:[Bool]",
        "The athlete's own safety answers. ``conditions`` names diet-policy exclusion ids; ``scoffAnswers`` "
        "holds one answer per SCOFF question, so reopening setup shows what was answered.",
    ),
    _model(
        "DietProfile",
        "sex:EquationSex birthYear:Int heightCm:Number activity:ActivityLevel goal:DietGoal pattern:DietPattern "
        "cuisines:[String] trainingLoad?:TrainingLoad bodyFatPercent?:Number screening:DietScreening "
        "pace?:AdaptationPace",
        "What the diet engine needs. ``sex`` selects the published equation; body fat is optional and never "
        "estimated; ``pace`` is how quickly targets follow the weight trend (the policy default when absent).",
    ),
    _model(
        "WeighIn",
        "id:UUID kg:Number measuredAt:Date source:String timeZone:String utcOffsetSeconds:Int",
        "One body-weight measurement, typed by the athlete (``manual``) or read from Apple Health (``appleHealth``). "
        "``utcOffsetSeconds`` is the local offset when it was taken, so the core can keep one reading per local day.",
    ),
    _model(
        "DietTargets",
        "energyKcal:Int proteinG:Int carbohydrateG:Int fatG:Int fibreG:Int policyVersion:String basis:String "
        "setAt:Date",
        "Daily targets the athlete accepted. ``basis`` says why: setup, profileChange or adjustment.",
    ),
    _model(
        "DietDecision",
        "id:UUID kind:String targets:DietTargets reason:String decidedAt:Date status:RecommendationStatus",
        "An accepted or rejected diet suggestion, kept as history.",
    ),
    _model(
        "WorkoutCues",
        "afterSet?:String restOver?:String next?:String",
        "What the spoken coach says (ADR-022), built from the plan and logged sets only. Empty without a workout.",
    ),
    _model(
        "PlateLoad",
        "perSide:[Number] total:Number exact:Bool",
        "Plates for each side of a barbell from the athlete's own bar and plates (ADR-021).",
    ),
    _model(
        "MuscleRing",
        "muscle:String done:Number planned:Number target:Number",
        "One major muscle this week: sets logged, sets the accepted week prescribes, and the weekly target.",
    ),
    _model(
        "WeekRings",
        "weekStart:Date muscles:[MuscleRing]",
        "This week's muscle rings from the athlete's local Monday (ADR-020). Counted from logged sets only.",
    ),
    _model(
        "StatusPeriod",
        "id:UUID kind:StatusKind startedAt:Date endsAt?:Date endedAt?:Date",
        "A period the athlete marked as on a break, sick or injured. While active, automatic proposals and "
        "plan adaptation pause, and its days do not count as missed (ADR-019).",
    ),
    _model(
        "State",
        "schemaVersion:Int athleteID:UUID revision:Int contextRevision:Int profile?:Profile program?:Program "
        "nextPlanOverride?:Plan previousPrograms:[Program] sessions:[Session] recommendations:[Recommendation] "
        "painExclusions:[String] audits:[Audit] conflicts:[Conflict] operations:[UUID] events:[Event] meals:[Meal] "
        "mealAudits:[MealAudit] recipes:[Recipe] dietProfile?:DietProfile weighIns:[WeighIn] "
        "dietTargets?:DietTargets dietDecisions:[DietDecision] excludedWeighIns:[Date] "
        "statusPeriods:[StatusPeriod]",
        "Everything the app persists. One file, one athlete.",
    ),
    _model(
        "CatalogExercise",
        "id:String name:String force?:String level:String mechanic?:String equipment?:String "
        "primaryMuscles:[String] secondaryMuscles:[String] instructions:[String] category:String images:[String] "
        "evidence?:[CatalogEvidence]",
        "Descriptive record from free-exercise-db. Never a governed Exercise. ``evidence`` is added by "
        "``scripts/annotate_catalog.py`` and absent when no reviewed research covers the exercise.",
    ),
    _model(
        "CatalogEvidence",
        "findingID:String outcome:String muscles:[String] result:String finding:String certainty:String "
        "design:String citation:String locator:String fullTextRead:Bool doi?:String pmid?:String",
        "What one cited study found about a catalog exercise. Descriptive only: never feeds progression.",
    ),
    _model(
        "SlotStatus",
        "slotID:UUID reason:String tone:String title:String body:String action?:String",
        "What Today shows under one slot: a needs-state, a paused state or a kept plan.",
    ),
    _model(
        "ProposalCard",
        "recommendationID:UUID kind:String slotID?:UUID title:String body:String",
        "A pending recommendation as Today shows it. Accept and reject still go through state commands.",
    ),
    _model(
        "TodayStatus",
        "slots:[SlotStatus] proposals:[ProposalCard] autoRequest?:UUID autoReplan?:Bool status?:StatusPeriod",
        "Read-only Today view model. ``autoRequest`` names one slot whose progression the host may request; "
        "``autoReplan`` says the host may request a week that fits recent attendance (ADR-018).",
    ),
    _model("ProgressEntry", "sessionID:UUID date:Date summary:String", "One recorded session as logged."),
    _model(
        "ExerciseProgress",
        "exerciseID:String name:String unit:Unit load?:Number unchangedSessions:Int entries:[ProgressEntry]",
        "Recorded values for one exercise, newest first. Nothing is estimated or projected.",
    ),
    _model(
        "WeightTrend",
        "latestKg:Number weeklyChangeKg:Number weeklyChangeFraction:Number weighIns:Int windowDays:Int",
        "The least-squares weight trend over the policy window. Absent until enough weigh-ins exist.",
    ),
    _model(
        "DietAdjustment",
        "targets:DietTargets reason:String title:String body:String",
        "A suggested change to the daily targets. Inert until the athlete accepts it.",
    ),
    _model("FoodPortion", "label:String grams:Number", "A household portion from USDA FoodData Central."),
    _model(
        "FoodSuggestion",
        "foodID:Int name:String portion:FoodPortion nutrients:Nutrients reason:String",
        "A food that fits what is left of today's targets.",
    ),
    _model(
        "DietCitation",
        "parameter:String value:String citation:String locator:String certainty:String",
        "Why a target is what it is: the value and the research behind it.",
    ),
    _model(
        "DietView",
        "status:DietStatus reason:String message:String targets?:DietTargets eaten:Nutrients remaining?:Nutrients "
        "trend?:WeightTrend adjustment?:DietAdjustment suggestions:[FoodSuggestion] notes:[String] "
        "citations:[DietCitation] policyVersion:String",
        "Read-only Diet tab model. In a preview, ``targets`` is what accepting the profile would set.",
    ),
    _model(
        "Views",
        "today:TodayStatus progress:[ExerciseProgress] diet:DietView rings?:WeekRings",
        "Everything the tab screens derive from state, computed in one pass after each change.",
    ),
    _model(
        "FoodItem",
        "id:Int name:String category:String per100g:Nutrients fibre?:Number portions:[FoodPortion] "
        "patterns:[DietPattern]",
        "One USDA FoodData Central food for logging (public domain, CC0).",
    ),
    _model("ChoiceOption", "id:String title:String detail:String", "One selectable option the setup screen shows."),
    _model(
        "DietOptions",
        "activityLevels:[ChoiceOption] goals:[ChoiceOption] patterns:[ChoiceOption] cuisines:[ChoiceOption] "
        "trainingLoads:[ChoiceOption] exclusions:[ChoiceOption] scoffQuestions:[String] minimumAgeYears:Int "
        "paces:[ChoiceOption] defaultPace:AdaptationPace paceQuestion:String paceNote:String policyVersion:String",
        "What the diet setup screen offers, taken from the active diet policy.",
    ),
    _model(
        "RecoveryObservation",
        "id:UUID title:String value:String date:Date source:String",
        "A read-only HealthKit sample with provenance. Never a readiness score.",
    ),
    _model(
        "WeekSession",
        "weekday:Int name:String minutes:Number exercises:Int sets:Int",
        "One session of a weekly option: its day, session type, estimated minutes and working sets.",
    ),
    _model(
        "WeekOption",
        "id:String split:String name:String days:[Int] sessions:[WeekSession] sessionsPerWeek:Int "
        "weeklyMinutes:Number volume:String score:Number reasons:[String]",
        "One week the athlete may choose (ADR-017). ``volume`` is ``full`` or ``reduced`` (time-limited); "
        "``reasons`` are codes the host explains. Choosing it is still a proposal the athlete accepts.",
    ),
    _model(
        "SpokenSet",
        "exercise?:String reps?:Int load?:Number rir?:Int",
        "What the on-device language model read from the athlete's words. Only a draft: "
        "``readSet`` keeps a number only if the athlete said it.",
    ),
    _model(
        "SetPreview",
        "sessionID:UUID slotID:UUID exerciseID:String name:String index:Int kind:SetKind reps:Int "
        "load?:Number unit:Unit rir?:Int",
        "A set ready for the athlete to confirm. Saved only through ``saveSet`` after the athlete taps Save.",
    ),
    _model(
        "SetReading",
        "preview?:SetPreview question?:String ignored:[String]",
        "A ``preview`` when the set is complete, otherwise a ``question``. ``ignored`` names draft "
        "fields dropped because the athlete never said them.",
    ),
    _model(
        "ChatDraft",
        "topic:ChatTopic exercise?:String minutes?:Int days?:Int",
        "What the on-device language model read from a chat message (ADR-023). Only a draft: ``chat`` "
        "keeps a number or an exercise only if the athlete said it.",
    ),
    _model(
        "ChatAction",
        "kind:ChatActionKind title:String slotID?:UUID exerciseID?:String minutes?:Int status?:StatusKind "
        "endsAt?:Date message?:String draft?:ChatDraft",
        "A button under a chat answer. Nothing runs until the athlete taps it, and a plan change it "
        "starts is still a proposal the athlete accepts. ``ask`` sends ``message`` with ``draft`` as a "
        "new question.",
    ),
    _model(
        "ChatSource",
        "key:String citation:String doi?:String pmid?:String",
        "A study or official report an answer rests on, from the active content bundle.",
    ),
    _model(
        "ChatReply",
        "topic:ChatTopic reading:String lines:[String] actions:[ChatAction] sources:[ChatSource] ignored:[String]",
        "The core's answer to one chat message. ``reading`` says how the message was understood; "
        "``lines`` come from the athlete's records and the cited content, never from the model; "
        "``ignored`` names draft fields dropped because the athlete never said them.",
    ),
]

# Constraints the schema generator applies after building the models above.
INTEGER_BOUNDS: list[tuple[str, str, int, int]] = [
    ("Slot", "workingSets", 1, 1000),
    ("Policy", "requiredExposures", 1, 1000),
]
STATE_SCHEMA_VERSION = 5  # migrations.py upgrades older saved files

# Training request variants: kind -> ordered (field, type) pairs. A field whose name ends in ``?``
# may be left out of that variant.
REQUEST_KINDS: dict[str, list[tuple[str, str]]] = {
    "progression": [("slotID", "UUID")],
    "shorten": [("minutes", "Int")],
    "substitute": [("slotID", "UUID"), ("alternativeID", "String")],
    "reschedule": [("date", "Date")],
    "replan": [("utcOffset", "Int")],
    "changeDays": [("freeDays", "[Int]"), ("minutes?", "Int"), ("optionID?", "String")],
}


def request_model() -> ModelSpec:
    """``Request`` as one flat record (for Swift): ``kind`` plus every variant's fields, optional."""
    fields = [FieldSpec("kind", "String")]
    for variant_fields in REQUEST_KINDS.values():
        for marked_name, type_name in variant_fields:
            name = marked_name.rstrip("?")
            if all(existing.name != name for existing in fields):
                fields.append(FieldSpec(name, type_name, optional=True))
    return ModelSpec("Request", tuple(fields), "One training request. Which fields are set depends on ``kind``.")


# --------------------------------------------------------------------------- #
# Operations (request payloads) and results
# --------------------------------------------------------------------------- #

OPERATIONS: list[tuple[str, str]] = [
    ("decide", "state:State request:Request permitsFixtures:Bool now:Date"),
    ("initialProgram", "profile:Profile permitsFixtures:Bool now:Date ids:[UUID] optionID?:String"),
    ("weekOptions", "profile:Profile permitsFixtures:Bool"),
    ("library", "permitsFixtures:Bool"),
    ("migrateState", "state:Object"),
    ("nutrients", "nutrients:Nutrients servings:Number"),
    ("recovery", "observations:[RecoveryObservation]"),
    ("views", "state:State permitsFixtures:Bool now:Date dayStart?:Date utcOffset?:Int"),
    ("loadSteps", "base:Number step:Number"),
    ("plateLoad", "load:Number bar:Number plates:[Number]"),
    ("workoutCues", "state:State permitsFixtures:Bool now:Date"),
    ("dietOptions", "now:Date"),
    ("dietPreview", "state:State profile:DietProfile now:Date"),
    ("foods", "query:String pattern?:DietPattern limit:Int"),
    ("readSet", "state:State text:String draft:SpokenSet permitsFixtures:Bool"),
    ("chat", "state:State text:String draft:ChatDraft permitsFixtures:Bool now:Date dayStart?:Date utcOffset?:Int"),
]

# State commands: name -> arguments spec. Order matters for the generated union.
COMMANDS: dict[str, str] = {
    "acceptInitialPlan": "profile:Profile optionID?:String",
    "configureLoad": "slotID:UUID load?:Number options:[Number]",
    "start": "checkIn:CheckIn",
    "skip": "checkIn:CheckIn",
    "setPaused": "paused:Bool",
    "saveSet": (
        "sessionID:UUID slotID:UUID index:Int kind:SetKind load?:Number reps:Int rir?:Int logID:UUID operationID:UUID"
    ),
    "finish": "reason:Omission",
    "reportPain": "exerciseID:String",
    "exclude": "exerciseID:String excluded:Bool",
    "correctSet": "sessionID:UUID logID:UUID expectedRevision:Int load?:Number reps:Int rir?:Int",
    "resolveConflict": "id:UUID useIncoming:Bool",
    "deleteSession": "id:UUID",
    "setStatus": "status:StatusKind endsAt?:Date",
    "endStatus": "",
    "deleteMeal": "id:UUID",
    "saveMeal": "meal:Meal asRecipe:Bool",
    "requestChange": "request:Request",
    "acceptRecommendation": "id:UUID",
    "rejectRecommendation": "id:UUID reason?:String",
    "setDietTargets": "profile:DietProfile expected:DietTargets",
    "saveDietProfile": "profile:DietProfile",
    "logWeighIn": "weighIn:WeighIn",
    "importWeighIns": "weighIns:[WeighIn]",
    "deleteWeighIn": "id:UUID",
    "acceptDietAdjustment": "expected:DietTargets",
    "rejectDietAdjustment": "expected:DietTargets",
    "saveFoodMeal": "id:UUID foodID:Int grams:Number occurredAt:Date timeZone:String",
}
MIN_IDS = {"initialProgram": 6, "stateCommand": 10}

RESULT_MODELS: list[ModelSpec] = [
    _model("StateResult", "state:State value?:Bool decision?:Decision"),
    _model("RecoveryResult", "status:String reason:String observations:[RecoveryObservation]"),
    _model("Error", "code:String message:String"),
]
RESULT_TYPES: dict[str, str] = {
    "decide": "Decision",
    "initialProgram": "Program",
    "weekOptions": "[WeekOption]",
    "library": "Library",
    "migrateState": "State",
    "nutrients": "Nutrients",
    "stateCommand": "StateResult",
    "recovery": "RecoveryResult",
    "views": "Views",
    "loadSteps": "[Number]",
    "plateLoad": "PlateLoad",
    "workoutCues": "WorkoutCues",
    "dietOptions": "DietOptions",
    "dietPreview": "DietView",
    "foods": "[FoodItem]",
    "readSet": "SetReading",
    "chat": "ChatReply",
}

# --------------------------------------------------------------------------- #
# Swift-only metadata
# --------------------------------------------------------------------------- #


class SwiftModel:
    """How a schema model appears in Swift. Absent models are hand-written."""

    __slots__ = ("defaults", "identifiable", "sets", "swift_name")

    def __init__(
        self,
        swift_name: str,
        defaults: dict[str, str] | None = None,  # field -> Swift default expression
        sets: frozenset[str] = frozenset(),  # fields encoded as arrays but held as Swift Sets
        identifiable: bool = False,
    ) -> None:
        self.swift_name = swift_name
        self.defaults = dict(defaults or {})
        self.sets = sets
        self.identifiable = identifiable


SWIFT_ENUMS: dict[str, tuple[str, bool]] = {  # schema enum -> (Swift name, CaseIterable)
    "Review": ("ReviewStatus", False),
    "Unit": ("MassUnit", True),
    "Basis": ("LoadBasis", True),
    "SessionStatus": ("SessionStatus", False),
    "SetKind": ("SetKind", False),
    "Outcome": ("DecisionOutcome", False),
    "RecommendationStatus": ("RecommendationStatus", False),
    "Omission": ("OmissionReason", True),
    "StatusKind": ("StatusKind", True),
    "DietGoal": ("DietGoal", True),
    "DietPattern": ("DietPattern", True),
    "ActivityLevel": ("ActivityLevel", True),
    "EquationSex": ("EquationSex", True),
    "TrainingLoad": ("TrainingLoad", True),
    "DietStatus": ("DietStatus", False),
    "AdaptationPace": ("AdaptationPace", True),
    "ChatTopic": ("ChatTopic", True),
    "ChatActionKind": ("ChatActionKind", False),
}

SWIFT_TYPE_NAMES: dict[str, str] = {
    "String": "String",
    "Number": "Double",
    "Int": "Int",
    "Bool": "Bool",
    "UUID": "UUID",
    "Date": "Date",
    "Omissions": "[String: OmissionReason]",
}

SWIFT_MODELS: dict[str, SwiftModel] = {
    "Profile": SwiftModel(
        "Profile",
        defaults={
            "adultConfirmed": "false",
            "supportedScopeConfirmed": "false",
            "goal": '"Hypertrophy"',
            "experience": '"Beginner"',
            "daysPerWeek": "3",
            "minutes": "45",
            "equipment": '["dumbbell"]',
            "preferredUnit": ".lb",
            "timeZone": "TimeZone.current.identifier",
            "excludedExercises": "[]",
            "preferredExercises": "[]",
            "freeDays": "nil",
            "minutesByDay": "nil",
        },
        sets=frozenset({"equipment", "excludedExercises", "preferredExercises"}),
    ),
    "Equipment": SwiftModel("EquipmentContext", defaults={"availableLoads": "[]"}, identifiable=True),
    "Exercise": SwiftModel(
        "Exercise", defaults={"review": ".fixture", "contentVersion": '"fixture-1"'}, identifiable=True
    ),
    "Policy": SwiftModel("TrainingPolicy"),
    "Library": SwiftModel("ContentLibrary"),
    "Request": SwiftModel(
        "TrainingRequest",
        defaults={
            "slotID": "nil",
            "minutes": "nil",
            "alternativeID": "nil",
            "date": "nil",
            "utcOffset": "nil",
            "freeDays": "nil",
            "optionID": "nil",
        },
    ),
    "Slot": SwiftModel("Prescription", defaults={"id": "UUID()", "load": "nil"}, identifiable=True),
    "Plan": SwiftModel(
        "SessionPlan",
        defaults={
            "id": "UUID()",
            "revision": "1",
            "modified": "false",
            "scheduledDate": "nil",
            "warmUpMinutes": "5",
            "weekday": "nil",
        },
        identifiable=True,
    ),
    "Program": SwiftModel(
        "Program", defaults={"id": "UUID()", "revision": "1", "sequenceIndex": "0"}, identifiable=True
    ),
    "CheckIn": SwiftModel(
        "CheckIn",
        defaults={
            "energy": "nil",
            "soreness": "nil",
            "painReported": "false",
            "minutes": "nil",
            "unavailableEquipment": "[]",
            "occurredAt": "Date()",
        },
        sets=frozenset({"unavailableEquipment"}),
    ),
    "SetLog": SwiftModel(
        "SetLog",
        defaults={
            "id": "UUID()",
            "operationID": "UUID()",
            "revision": "1",
            "load": "nil",
            "rir": "nil",
            "conflicted": "false",
        },
        identifiable=True,
    ),
    "Session": SwiftModel(
        "WorkoutSession",
        defaults={
            "id": "UUID()",
            "status": ".inProgress",
            "endedAt": "nil",
            "logs": "[]",
            "omissions": "[:]",
            "restEndsAt": "nil",
        },
        identifiable=True,
    ),
    "Evidence": SwiftModel("Evidence", identifiable=True),
    "Decision": SwiftModel("Decision", defaults={"after": "nil", "evidence": "[]", "week": "nil"}),
    "Recommendation": SwiftModel(
        "Recommendation", defaults={"id": "UUID()", "status": ".proposed", "rejectionReason": "nil"}, identifiable=True
    ),
    "Audit": SwiftModel("AuditEntry", defaults={"id": "UUID()"}, identifiable=True),
    "Conflict": SwiftModel("Conflict", defaults={"id": "UUID()"}, identifiable=True),
    "Event": SwiftModel("AnalyticsEvent", defaults={"id": "UUID()", "reason": "nil"}, identifiable=True),
    "Nutrients": SwiftModel("Nutrients", defaults={"calories": "0", "protein": "0", "carbs": "0", "fat": "0"}),
    "Meal": SwiftModel(
        "Meal",
        defaults={
            "id": "UUID()",
            "revision": "1",
            "occurredAt": "Date()",
            "source": '"user_confirmed_estimate"',
            "timeZone": "TimeZone.current.identifier",
        },
        identifiable=True,
    ),
    "MealAudit": SwiftModel("MealAudit", defaults={"id": "UUID()"}, identifiable=True),
    "Recipe": SwiftModel("Recipe", defaults={"id": "UUID()", "source": '"user_estimate"'}, identifiable=True),
    "State": SwiftModel(
        "AthleteState",
        defaults={
            "schemaVersion": "5",
            "athleteID": "UUID()",
            "revision": "0",
            "contextRevision": "0",
            "profile": "nil",
            "program": "nil",
            "nextPlanOverride": "nil",
            "previousPrograms": "[]",
            "sessions": "[]",
            "recommendations": "[]",
            "painExclusions": "[]",
            "audits": "[]",
            "conflicts": "[]",
            "operations": "[]",
            "events": "[]",
            "meals": "[]",
            "mealAudits": "[]",
            "recipes": "[]",
            "dietProfile": "nil",
            "weighIns": "[]",
            "dietTargets": "nil",
            "dietDecisions": "[]",
            "excludedWeighIns": "[]",
            "statusPeriods": "[]",
        },
        sets=frozenset({"painExclusions", "operations"}),
    ),
    "DietScreening": SwiftModel(
        "DietScreening", defaults={"pregnant": "false", "lactating": "false", "conditions": "[]", "scoffAnswers": "[]"}
    ),
    "DietProfile": SwiftModel(
        "DietProfile",
        defaults={
            "sex": ".female",
            "birthYear": "1995",
            "heightCm": "170",
            "activity": ".lowActive",
            "goal": ".maintenance",
            "pattern": ".omnivore",
            "cuisines": "[]",
            "trainingLoad": "nil",
            "bodyFatPercent": "nil",
            "screening": "DietScreening()",
            "pace": "nil",
        },
    ),
    "WeighIn": SwiftModel(
        "WeighIn",
        defaults={
            "id": "UUID()",
            "source": '"manual"',
            "timeZone": "TimeZone.current.identifier",
            "utcOffsetSeconds": "TimeZone.current.secondsFromGMT()",
        },
        identifiable=True,
    ),
    "DietTargets": SwiftModel("DietTargets"),
    "DietDecision": SwiftModel("DietDecision", identifiable=True),
    "WeightTrend": SwiftModel("WeightTrend"),
    "DietAdjustment": SwiftModel("DietAdjustment"),
    "FoodPortion": SwiftModel("FoodPortion"),
    "FoodSuggestion": SwiftModel("FoodSuggestion"),
    "DietCitation": SwiftModel("DietCitation"),
    "DietView": SwiftModel(
        "DietView",
        defaults={
            "status": ".needsInput",
            "reason": '"NO_DIET_PROFILE"',
            "message": '""',
            "targets": "nil",
            "eaten": "Nutrients()",
            "remaining": "nil",
            "trend": "nil",
            "adjustment": "nil",
            "suggestions": "[]",
            "notes": "[]",
            "citations": "[]",
            "policyVersion": '""',
        },
    ),
    "FoodItem": SwiftModel("FoodItem", defaults={"fibre": "nil"}, identifiable=True),
    "ChoiceOption": SwiftModel("ChoiceOption", identifiable=True),
    "DietOptions": SwiftModel("DietOptions"),
    "CatalogExercise": SwiftModel("CatalogExercise", defaults={"evidence": "nil"}, identifiable=True),
    "CatalogEvidence": SwiftModel("CatalogEvidence", defaults={"doi": "nil", "pmid": "nil"}),
    "SlotStatus": SwiftModel("SlotStatus", defaults={"action": "nil"}),
    "ProposalCard": SwiftModel("ProposalCard", defaults={"slotID": "nil"}),
    "TodayStatus": SwiftModel(
        "TodayStatus",
        defaults={"slots": "[]", "proposals": "[]", "autoRequest": "nil", "autoReplan": "nil", "status": "nil"},
    ),
    "ProgressEntry": SwiftModel("ProgressEntry"),
    "ExerciseProgress": SwiftModel("ExerciseProgress", defaults={"load": "nil"}),
    "StatusPeriod": SwiftModel("StatusPeriod", defaults={"endsAt": "nil", "endedAt": "nil"}, identifiable=True),
    "PlateLoad": SwiftModel("PlateLoad"),
    "WorkoutCues": SwiftModel("WorkoutCues", defaults={"afterSet": "nil", "restOver": "nil", "next": "nil"}),
    "MuscleRing": SwiftModel("MuscleRing"),
    "WeekRings": SwiftModel("WeekRings"),
    "WeekSession": SwiftModel("WeekSession"),
    "WeekOption": SwiftModel("WeekOption", identifiable=True),
    "Views": SwiftModel(
        "CoreViews", defaults={"today": "TodayStatus()", "progress": "[]", "diet": "DietView()", "rings": "nil"}
    ),
    "SpokenSet": SwiftModel("SpokenSet", defaults={"exercise": "nil", "reps": "nil", "load": "nil", "rir": "nil"}),
    "SetPreview": SwiftModel("SetPreview", defaults={"load": "nil", "rir": "nil"}),
    "SetReading": SwiftModel("SetReading", defaults={"preview": "nil", "question": "nil", "ignored": "[]"}),
    "ChatDraft": SwiftModel("ChatDraft", defaults={"exercise": "nil", "minutes": "nil", "days": "nil"}),
    "ChatAction": SwiftModel(
        "ChatAction",
        defaults={
            "slotID": "nil",
            "exerciseID": "nil",
            "minutes": "nil",
            "status": "nil",
            "endsAt": "nil",
            "message": "nil",
            "draft": "nil",
        },
    ),
    "ChatSource": SwiftModel("ChatSource", defaults={"doi": "nil", "pmid": "nil"}),
    "ChatReply": SwiftModel("ChatReply"),
}
