"""The single source of truth for every record that crosses the Swift ⇄ Python boundary.

Two generators consume this module:

- ``scripts/generate_schemas.py``      → ``shared/schemas/v1/{request,response}.schema.json``
- ``scripts/generate_swift_models.py`` → ``apps/ios/Sources/AITrainerCore/Models.swift``

Change a record here, run both generators, commit all three outputs. CI diffs them.

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

PRIMITIVES: dict[str, str] = {"String": "string", "Number": "number", "Int": "integer", "Bool": "boolean"}

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


# Domain records, in ``$defs`` order. ``Omissions``, ``Request`` and ``StoredRequest``
# are structural definitions inserted by the schema generator at the marked positions.
MODELS: list[ModelSpec] = [
    _model(
        "Profile",
        "adultConfirmed:Bool supportedScopeConfirmed:Bool goal:String experience:String daysPerWeek:Int "
        "minutes:Int equipment:[String] preferredUnit:Unit timeZone:String excludedExercises:[String] "
        "preferredExercises:[String]",
        "What the athlete told us at onboarding. No body metrics, no estimated strength.",
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
    _model("Library", "exercises:[Exercise] policy:Policy permitsFixtures:Bool"),
    _model(
        "Slot",
        "id:UUID exerciseID:String equipment:Equipment protocolID:String workingSets:Int lowerReps:Int "
        "upperReps:Int targets:[Int] load?:Number restSeconds:Int optional:Bool estimatedMinutes:Int",
        "A prescription for one exercise in a session. ``load`` absent means unknown, never zero.",
    ),
    _model(
        "Plan",
        "id:UUID revision:Int name:String slots:[Slot] modified:Bool scheduledDate?:Date warmUpMinutes:Int",
        "One session's accepted prescriptions. ``modified`` marks a temporary shortened/substituted copy.",
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
        "outcome:Outcome reason:String explanation:String after?:Plan evidence:[Evidence]",
        "The Training Brain's answer. ``after`` is the proposed plan for ``proposeChange`` outcomes.",
    ),
    # -> Request and StoredRequest (tagged unions) are inserted here by the schema generator.
    _model(
        "Recommendation",
        "id:UUID stateRevision:Int contextRevision:Int targetPlanID:UUID targetPlanRevision:Int "
        "request:StoredRequest decision:Decision policyVersion:String createdAt:Date status:RecommendationStatus "
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
        "State",
        "schemaVersion:Int athleteID:UUID revision:Int contextRevision:Int profile?:Profile program?:Program "
        "nextPlanOverride?:Plan previousPrograms:[Program] sessions:[Session] recommendations:[Recommendation] "
        "painExclusions:[String] audits:[Audit] conflicts:[Conflict] operations:[UUID] events:[Event] meals:[Meal] "
        "mealAudits:[MealAudit] recipes:[Recipe]",
        "Everything the app persists. One file, one athlete.",
    ),
    _model(
        "CatalogExercise",
        "id:String name:String force?:String level:String mechanic?:String equipment?:String "
        "primaryMuscles:[String] secondaryMuscles:[String] instructions:[String] category:String images:[String]",
        "Descriptive record from free-exercise-db. Never a governed Exercise.",
    ),
]

# Constraints the schema generator applies after building the models above.
INTEGER_BOUNDS: list[tuple[str, str, int, int]] = [
    ("Slot", "workingSets", 1, 1000),
    ("Policy", "requiredExposures", 1, 1000),
]
STATE_SCHEMA_VERSION = 1

# Training request variants: kind -> ordered (field, type) pairs.
REQUEST_KINDS: dict[str, list[tuple[str, str]]] = {
    "progression": [("slotID", "UUID")],
    "shorten": [("minutes", "Int")],
    "substitute": [("slotID", "UUID"), ("alternativeID", "String")],
    "reschedule": [("date", "Date")],
}

# --------------------------------------------------------------------------- #
# Operations (request payloads) and results
# --------------------------------------------------------------------------- #

OPERATIONS: list[tuple[str, str]] = [
    ("decide", "state:State request:Request library:Library now:Date"),
    ("progression", "state:State plan:Plan slot:Slot policy:Policy now:Date"),
    ("initialProgram", "profile:Profile library:Library now:Date ids:[UUID]"),
    (
        "recommendation",
        "operation:String state:State request?:Request id?:UUID reason?:String library:Library now:Date ids:[UUID]",
    ),
    ("nutrients", "nutrients:Nutrients servings:Number"),
    ("performance", "state:State slot:Slot now:Date"),
    ("workingLogs", "session:Session slot:Slot"),
    ("validateSet", "log:SetLog"),
    ("catalog", "exercises:[CatalogExercise]"),
]
RECOVERY_OBSERVATION = _model(
    "RecoveryObservation",
    "id:UUID title:String value:String date:Date source:String",
    "A read-only HealthKit sample with provenance. Never a readiness score.",
)
RECOVERY_OPERATION: tuple[str, str] = ("recovery", "observations:[RecoveryObservation]")

# State commands: name -> arguments spec. Order matters for the generated union.
COMMANDS: dict[str, str] = {
    "acceptInitialPlan": "profile:Profile",
    "configureLoad": "slotID:UUID load?:Number options:[Number]",
    "start": "checkIn:CheckIn",
    "skip": "checkIn:CheckIn",
    "setPaused": "paused:Bool",
    "saveSet": "log:SetLog sessionID:UUID",
    "finish": "reason:Omission",
    "reportPain": "exerciseID:String",
    "exclude": "exerciseID:String excluded:Bool",
    "correctSet": "sessionID:UUID logID:UUID expectedRevision:Int load?:Number reps:Int rir?:Int",
    "resolveConflict": "id:UUID useIncoming:Bool",
    "deleteSession": "id:UUID",
    "deleteMeal": "id:UUID",
    "saveMeal": "meal:Meal asRecipe:Bool",
}
MIN_IDS = {"initialProgram": 6, "recommendation": 2, "stateCommand": 10}

RESULT_MODELS: list[ModelSpec] = [
    _model("StateResult", "state:State value?:Bool"),
    _model("RecommendationResult", "state:State decision?:Decision"),
    _model("RecoveryResult", "status:String reason:String observations:[RecoveryObservation]"),
    _model("Error", "code:String message:String"),
]
RESULT_TYPES: dict[str, str] = {
    "decide": "Decision",
    "progression": "Decision",
    "initialProgram": "Program",
    "stateCommand": "StateResult",
    "recommendation": "RecommendationResult",
    "nutrients": "Nutrients",
    "performance": "[Session]",
    "workingLogs": "[SetLog]",
    "validateSet": "Bool",
    "catalog": "[CatalogExercise]",
    "recovery": "RecoveryResult",
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
}

SWIFT_TYPE_NAMES: dict[str, str] = {
    "String": "String",
    "Number": "Double",
    "Int": "Int",
    "Bool": "Bool",
    "UUID": "UUID",
    "Date": "Date",
    "StoredRequest": "Request",  # hand-written Codable enum in Models+Helpers.swift
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
        },
        sets=frozenset({"equipment", "excludedExercises", "preferredExercises"}),
    ),
    "Equipment": SwiftModel("EquipmentContext", defaults={"availableLoads": "[]"}, identifiable=True),
    "Exercise": SwiftModel(
        "Exercise", defaults={"review": ".fixture", "contentVersion": '"fixture-1"'}, identifiable=True
    ),
    "Policy": SwiftModel("TrainingPolicy"),
    "Slot": SwiftModel("Prescription", defaults={"id": "UUID()", "load": "nil"}, identifiable=True),
    "Plan": SwiftModel(
        "SessionPlan",
        defaults={"id": "UUID()", "revision": "1", "modified": "false", "scheduledDate": "nil", "warmUpMinutes": "5"},
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
    "Decision": SwiftModel("Decision", defaults={"after": "nil", "evidence": "[]"}),
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
            "schemaVersion": "1",
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
        },
        sets=frozenset({"painExclusions", "operations"}),
    ),
    "CatalogExercise": SwiftModel("CatalogExercise", identifiable=True),
}
