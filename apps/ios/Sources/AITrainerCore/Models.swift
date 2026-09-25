// GENERATED FILE — do not edit by hand.
// Source of truth: core/python/ai_trainer/contract_spec.py
// Regenerate:      python3 scripts/generate_swift_models.py
//
// Codable records shared with the Python core. Field names and JSON shapes must match
// the v1 contract exactly. Behaviour lives in Models+Helpers.swift.

import Foundation

// MARK: - Enums

public enum ReviewStatus: String, Codable {
    case fixture, approved, disabled
}

public enum MassUnit: String, Codable, CaseIterable {
    case lb, kg
}

public enum LoadBasis: String, Codable, CaseIterable {
    case total, perHand, machineSetting, assistance, externalBodyweight
}

public enum SessionStatus: String, Codable {
    case inProgress, paused, completed, endedEarly, skipped
}

public enum SetKind: String, Codable {
    case working, warmUp, extra
}

public enum DecisionOutcome: String, Codable {
    case keepPlan, proposeChange, needsInput, unassessed, withholdGuidance
}

public enum RecommendationStatus: String, Codable {
    case proposed, applied, rejected, expired
}

public enum OmissionReason: String, Codable, CaseIterable {
    case time, equipment, userChoice, pain, interruption, unspecified
}

public enum StatusKind: String, Codable, CaseIterable {
    case onBreak, sick, injured
}

public enum DietGoal: String, Codable, CaseIterable {
    case fatLoss, muscleGain, maintenance, endurance
}

public enum DietPattern: String, Codable, CaseIterable {
    case omnivore, vegetarian, vegan
}

public enum ActivityLevel: String, Codable, CaseIterable {
    case inactive, lowActive, active, veryActive
}

public enum EquationSex: String, Codable, CaseIterable {
    case female, male
}

public enum TrainingLoad: String, Codable, CaseIterable {
    case light, moderate, high, veryHigh
}

public enum DietStatus: String, Codable {
    case ready, needsInput, withheld
}

public enum AdaptationPace: String, Codable, CaseIterable {
    case slower, standard
}

// MARK: - Records

/// What the athlete told us at onboarding. No body metrics, no estimated strength. ``freeDays`` are weekdays 0-6 (Monday = 0) and ``minutesByDay`` maps a weekday to that day's minutes; both stay absent until the athlete gives them (ADR-017).
public struct Profile: Codable, Equatable {
    public var adultConfirmed: Bool
    public var supportedScopeConfirmed: Bool
    public var goal: String
    public var experience: String
    public var daysPerWeek: Int
    public var minutes: Int
    public var equipment: Set<String>
    public var preferredUnit: MassUnit
    public var timeZone: String
    public var excludedExercises: Set<String>
    public var preferredExercises: Set<String>
    public var freeDays: [Int]?
    public var minutesByDay: [String: Int]?

    public init(
        adultConfirmed: Bool = false,
        supportedScopeConfirmed: Bool = false,
        goal: String = "Hypertrophy",
        experience: String = "Beginner",
        daysPerWeek: Int = 3,
        minutes: Int = 45,
        equipment: Set<String> = ["dumbbell"],
        preferredUnit: MassUnit = .lb,
        timeZone: String = TimeZone.current.identifier,
        excludedExercises: Set<String> = [],
        preferredExercises: Set<String> = [],
        freeDays: [Int]? = nil,
        minutesByDay: [String: Int]? = nil
    ) {
        self.adultConfirmed = adultConfirmed
        self.supportedScopeConfirmed = supportedScopeConfirmed
        self.goal = goal
        self.experience = experience
        self.daysPerWeek = daysPerWeek
        self.minutes = minutes
        self.equipment = equipment
        self.preferredUnit = preferredUnit
        self.timeZone = timeZone
        self.excludedExercises = excludedExercises
        self.preferredExercises = preferredExercises
        self.freeDays = freeDays
        self.minutesByDay = minutesByDay
    }
}

/// One physical piece of equipment as the athlete identifies it. Loads never transfer between identities.
public struct EquipmentContext: Codable, Equatable, Identifiable {
    public var id: String
    public var name: String
    public var kind: String
    public var unit: MassUnit
    public var basis: LoadBasis
    public var availableLoads: [Double]

    public init(
        id: String,
        name: String,
        kind: String,
        unit: MassUnit,
        basis: LoadBasis,
        availableLoads: [Double] = []
    ) {
        self.id = id
        self.name = name
        self.kind = kind
        self.unit = unit
        self.basis = basis
        self.availableLoads = availableLoads
    }
}

/// A governed library exercise. ``alternatives`` are directional curated substitutes.
public struct Exercise: Codable, Equatable, Identifiable {
    public var id: String
    public var name: String
    public var role: String
    public var equipmentKind: String
    public var basis: LoadBasis
    public var alternatives: [String]
    public var review: ReviewStatus
    public var contentVersion: String

    public init(
        id: String,
        name: String,
        role: String,
        equipmentKind: String,
        basis: LoadBasis,
        alternatives: [String],
        review: ReviewStatus = .fixture,
        contentVersion: String = "fixture-1"
    ) {
        self.id = id
        self.name = name
        self.role = role
        self.equipmentKind = equipmentKind
        self.basis = basis
        self.alternatives = alternatives
        self.review = review
        self.contentVersion = contentVersion
    }
}

/// Progression policy parameters. Values are supplied by the content bundle, never assumed.
public struct TrainingPolicy: Codable, Equatable {
    public var id: String
    public var version: String
    public var review: ReviewStatus
    public var requiredExposures: Int
    public var minimumRIR: Int
    public var maximumIncreaseFraction: Double
    public var historyDays: Int
    public var maximumGapDays: Int

    public init(
        id: String,
        version: String,
        review: ReviewStatus,
        requiredExposures: Int,
        minimumRIR: Int,
        maximumIncreaseFraction: Double,
        historyDays: Int,
        maximumGapDays: Int
    ) {
        self.id = id
        self.version = version
        self.review = review
        self.requiredExposures = requiredExposures
        self.minimumRIR = minimumRIR
        self.maximumIncreaseFraction = maximumIncreaseFraction
        self.historyDays = historyDays
        self.maximumGapDays = maximumGapDays
    }
}

/// The bundled content the core runs against, as the host displays it.
public struct ContentLibrary: Codable, Equatable {
    public var exercises: [Exercise]
    public var policy: TrainingPolicy
    public var permitsFixtures: Bool

    public init(
        exercises: [Exercise],
        policy: TrainingPolicy,
        permitsFixtures: Bool
    ) {
        self.exercises = exercises
        self.policy = policy
        self.permitsFixtures = permitsFixtures
    }
}

/// A prescription for one exercise in a session. ``load`` absent means unknown, never zero.
public struct Prescription: Codable, Equatable, Identifiable {
    public var id: UUID
    public var exerciseID: String
    public var equipment: EquipmentContext
    public var protocolID: String
    public var workingSets: Int
    public var lowerReps: Int
    public var upperReps: Int
    public var targets: [Int]
    public var load: Double?
    public var restSeconds: Int
    public var optional: Bool
    public var estimatedMinutes: Int

    public init(
        id: UUID = UUID(),
        exerciseID: String,
        equipment: EquipmentContext,
        protocolID: String,
        workingSets: Int,
        lowerReps: Int,
        upperReps: Int,
        targets: [Int],
        load: Double? = nil,
        restSeconds: Int,
        optional: Bool,
        estimatedMinutes: Int
    ) {
        self.id = id
        self.exerciseID = exerciseID
        self.equipment = equipment
        self.protocolID = protocolID
        self.workingSets = workingSets
        self.lowerReps = lowerReps
        self.upperReps = upperReps
        self.targets = targets
        self.load = load
        self.restSeconds = restSeconds
        self.optional = optional
        self.estimatedMinutes = estimatedMinutes
    }
}

/// One session's accepted prescriptions. ``modified`` marks a temporary shortened/substituted copy. ``weekday`` (0-6, Monday = 0) is the day a weekly plan (ADR-017) puts this session on.
public struct SessionPlan: Codable, Equatable, Identifiable {
    public var id: UUID
    public var revision: Int
    public var name: String
    public var slots: [Prescription]
    public var modified: Bool
    public var scheduledDate: Date?
    public var warmUpMinutes: Int
    public var weekday: Int?

    public init(
        id: UUID = UUID(),
        revision: Int = 1,
        name: String,
        slots: [Prescription],
        modified: Bool = false,
        scheduledDate: Date? = nil,
        warmUpMinutes: Int = 5,
        weekday: Int? = nil
    ) {
        self.id = id
        self.revision = revision
        self.name = name
        self.slots = slots
        self.modified = modified
        self.scheduledDate = scheduledDate
        self.warmUpMinutes = warmUpMinutes
        self.weekday = weekday
    }
}

/// The accepted sequence of session plans; ``sequenceIndex`` points at the next one.
public struct Program: Codable, Equatable, Identifiable {
    public var id: UUID
    public var revision: Int
    public var templateID: String
    public var libraryVersion: String
    public var plans: [SessionPlan]
    public var sequenceIndex: Int
    public var acceptedAt: Date

    public init(
        id: UUID = UUID(),
        revision: Int = 1,
        templateID: String,
        libraryVersion: String,
        plans: [SessionPlan],
        sequenceIndex: Int = 0,
        acceptedAt: Date
    ) {
        self.id = id
        self.revision = revision
        self.templateID = templateID
        self.libraryVersion = libraryVersion
        self.plans = plans
        self.sequenceIndex = sequenceIndex
        self.acceptedAt = acceptedAt
    }
}

/// Subjective pre-session input. Recorded, never scored.
public struct CheckIn: Codable, Equatable {
    public var energy: String?
    public var soreness: String?
    public var painReported: Bool
    public var minutes: Int?
    public var unavailableEquipment: Set<String>
    public var occurredAt: Date

    public init(
        energy: String? = nil,
        soreness: String? = nil,
        painReported: Bool = false,
        minutes: Int? = nil,
        unavailableEquipment: Set<String> = [],
        occurredAt: Date = Date()
    ) {
        self.energy = energy
        self.soreness = soreness
        self.painReported = painReported
        self.minutes = minutes
        self.unavailableEquipment = unavailableEquipment
        self.occurredAt = occurredAt
    }
}

/// What actually happened in one set. ``operationID`` makes saves idempotent.
public struct SetLog: Codable, Equatable, Identifiable {
    public var id: UUID
    public var operationID: UUID
    public var revision: Int
    public var prescriptionID: UUID
    public var contextKey: String
    public var index: Int
    public var kind: SetKind
    public var load: Double?
    public var unit: MassUnit
    public var basis: LoadBasis
    public var reps: Int
    public var rir: Int?
    public var occurredAt: Date
    public var conflicted: Bool

    public init(
        id: UUID = UUID(),
        operationID: UUID = UUID(),
        revision: Int = 1,
        prescriptionID: UUID,
        contextKey: String,
        index: Int,
        kind: SetKind,
        load: Double? = nil,
        unit: MassUnit,
        basis: LoadBasis,
        reps: Int,
        rir: Int? = nil,
        occurredAt: Date,
        conflicted: Bool = false
    ) {
        self.id = id
        self.operationID = operationID
        self.revision = revision
        self.prescriptionID = prescriptionID
        self.contextKey = contextKey
        self.index = index
        self.kind = kind
        self.load = load
        self.unit = unit
        self.basis = basis
        self.reps = reps
        self.rir = rir
        self.occurredAt = occurredAt
        self.conflicted = conflicted
    }
}

/// A workout from start to summary. Keeps the original and the accepted plan for provenance.
public struct WorkoutSession: Codable, Equatable, Identifiable {
    public var id: UUID
    public var programID: UUID
    public var programRevision: Int
    public var originalPlan: SessionPlan
    public var plan: SessionPlan
    public var status: SessionStatus
    public var startedAt: Date
    public var endedAt: Date?
    public var timeZone: String
    public var checkIn: CheckIn
    public var logs: [SetLog]
    public var omissions: [String: OmissionReason]
    public var restEndsAt: Date?

    public init(
        id: UUID = UUID(),
        programID: UUID,
        programRevision: Int,
        originalPlan: SessionPlan,
        plan: SessionPlan,
        status: SessionStatus = .inProgress,
        startedAt: Date,
        endedAt: Date? = nil,
        timeZone: String,
        checkIn: CheckIn,
        logs: [SetLog] = [],
        omissions: [String: OmissionReason] = [:],
        restEndsAt: Date? = nil
    ) {
        self.id = id
        self.programID = programID
        self.programRevision = programRevision
        self.originalPlan = originalPlan
        self.plan = plan
        self.status = status
        self.startedAt = startedAt
        self.endedAt = endedAt
        self.timeZone = timeZone
        self.checkIn = checkIn
        self.logs = logs
        self.omissions = omissions
        self.restEndsAt = restEndsAt
    }
}

/// A set log id/revision a decision relied on.
public struct Evidence: Codable, Equatable, Identifiable {
    public var id: UUID
    public var revision: Int

    public init(
        id: UUID,
        revision: Int
    ) {
        self.id = id
        self.revision = revision
    }
}

/// The Training Brain's answer. ``after`` is the proposed plan for ``proposeChange`` outcomes; ``week`` is the proposed week for a ``replan`` (ADR-018), built into a program only when accepted.
public struct Decision: Codable, Equatable {
    public var outcome: DecisionOutcome
    public var reason: String
    public var explanation: String
    public var after: SessionPlan?
    public var evidence: [Evidence]
    public var week: WeekOption?

    public init(
        outcome: DecisionOutcome,
        reason: String,
        explanation: String,
        after: SessionPlan? = nil,
        evidence: [Evidence] = [],
        week: WeekOption? = nil
    ) {
        self.outcome = outcome
        self.reason = reason
        self.explanation = explanation
        self.after = after
        self.evidence = evidence
        self.week = week
    }
}

/// One training request. Which fields are set depends on ``kind``.
public struct TrainingRequest: Codable, Equatable {
    public var kind: String
    public var slotID: UUID?
    public var minutes: Int?
    public var alternativeID: String?
    public var date: Date?
    public var utcOffset: Int?

    public init(
        kind: String,
        slotID: UUID? = nil,
        minutes: Int? = nil,
        alternativeID: String? = nil,
        date: Date? = nil,
        utcOffset: Int? = nil
    ) {
        self.kind = kind
        self.slotID = slotID
        self.minutes = minutes
        self.alternativeID = alternativeID
        self.date = date
        self.utcOffset = utcOffset
    }
}

/// A proposal pinned to the context it was computed against. Inert until accepted.
public struct Recommendation: Codable, Equatable, Identifiable {
    public var id: UUID
    public var stateRevision: Int
    public var contextRevision: Int
    public var targetPlanID: UUID
    public var targetPlanRevision: Int
    public var request: TrainingRequest
    public var decision: Decision
    public var policyVersion: String
    public var createdAt: Date
    public var status: RecommendationStatus
    public var rejectionReason: String?

    public init(
        id: UUID = UUID(),
        stateRevision: Int,
        contextRevision: Int,
        targetPlanID: UUID,
        targetPlanRevision: Int,
        request: TrainingRequest,
        decision: Decision,
        policyVersion: String,
        createdAt: Date,
        status: RecommendationStatus = .proposed,
        rejectionReason: String? = nil
    ) {
        self.id = id
        self.stateRevision = stateRevision
        self.contextRevision = contextRevision
        self.targetPlanID = targetPlanID
        self.targetPlanRevision = targetPlanRevision
        self.request = request
        self.decision = decision
        self.policyVersion = policyVersion
        self.createdAt = createdAt
        self.status = status
        self.rejectionReason = rejectionReason
    }
}

/// The set log a correction replaced.
public struct AuditEntry: Codable, Equatable, Identifiable {
    public var id: UUID
    public var previous: SetLog
    public var correctedAt: Date

    public init(
        id: UUID = UUID(),
        previous: SetLog,
        correctedAt: Date
    ) {
        self.id = id
        self.previous = previous
        self.correctedAt = correctedAt
    }
}

/// Two competing versions of one set. Resolved explicitly by the athlete, never silently.
public struct Conflict: Codable, Equatable, Identifiable {
    public var id: UUID
    public var sessionID: UUID
    public var current: SetLog
    public var incoming: SetLog

    public init(
        id: UUID = UUID(),
        sessionID: UUID,
        current: SetLog,
        incoming: SetLog
    ) {
        self.id = id
        self.sessionID = sessionID
        self.current = current
        self.incoming = incoming
    }
}

/// Local analytics event.
public struct AnalyticsEvent: Codable, Equatable, Identifiable {
    public var id: UUID
    public var name: String
    public var occurredAt: Date
    public var stateRevision: Int
    public var reason: String?

    public init(
        id: UUID = UUID(),
        name: String,
        occurredAt: Date,
        stateRevision: Int,
        reason: String? = nil
    ) {
        self.id = id
        self.name = name
        self.occurredAt = occurredAt
        self.stateRevision = stateRevision
        self.reason = reason
    }
}

public struct Nutrients: Codable, Equatable {
    public var calories: Double
    public var protein: Double
    public var carbs: Double
    public var fat: Double

    public init(
        calories: Double = 0,
        protein: Double = 0,
        carbs: Double = 0,
        fat: Double = 0
    ) {
        self.calories = calories
        self.protein = protein
        self.carbs = carbs
        self.fat = fat
    }
}

/// A user-confirmed nutrient estimate for one eaten portion.
public struct Meal: Codable, Equatable, Identifiable {
    public var id: UUID
    public var revision: Int
    public var name: String
    public var nutrients: Nutrients
    public var occurredAt: Date
    public var source: String
    public var timeZone: String

    public init(
        id: UUID = UUID(),
        revision: Int = 1,
        name: String,
        nutrients: Nutrients,
        occurredAt: Date = Date(),
        source: String = "user_confirmed_estimate",
        timeZone: String = TimeZone.current.identifier
    ) {
        self.id = id
        self.revision = revision
        self.name = name
        self.nutrients = nutrients
        self.occurredAt = occurredAt
        self.source = source
        self.timeZone = timeZone
    }
}

public struct MealAudit: Codable, Equatable, Identifiable {
    public var id: UUID
    public var previous: Meal
    public var correctedAt: Date

    public init(
        id: UUID = UUID(),
        previous: Meal,
        correctedAt: Date
    ) {
        self.id = id
        self.previous = previous
        self.correctedAt = correctedAt
    }
}

/// An immutable saved portion.
public struct Recipe: Codable, Equatable, Identifiable {
    public var id: UUID
    public var name: String
    public var perServing: Nutrients
    public var source: String

    public init(
        id: UUID = UUID(),
        name: String,
        perServing: Nutrients,
        source: String = "user_estimate"
    ) {
        self.id = id
        self.name = name
        self.perServing = perServing
        self.source = source
    }
}

/// The athlete's own safety answers. ``conditions`` names diet-policy exclusion ids; ``scoffAnswers`` holds one answer per SCOFF question, so reopening setup shows what was answered.
public struct DietScreening: Codable, Equatable {
    public var pregnant: Bool
    public var lactating: Bool
    public var conditions: [String]
    public var scoffAnswers: [Bool]

    public init(
        pregnant: Bool = false,
        lactating: Bool = false,
        conditions: [String] = [],
        scoffAnswers: [Bool] = []
    ) {
        self.pregnant = pregnant
        self.lactating = lactating
        self.conditions = conditions
        self.scoffAnswers = scoffAnswers
    }
}

/// What the diet engine needs. ``sex`` selects the published equation; body fat is optional and never estimated; ``pace`` is how quickly targets follow the weight trend (the policy default when absent).
public struct DietProfile: Codable, Equatable {
    public var sex: EquationSex
    public var birthYear: Int
    public var heightCm: Double
    public var activity: ActivityLevel
    public var goal: DietGoal
    public var pattern: DietPattern
    public var cuisines: [String]
    public var trainingLoad: TrainingLoad?
    public var bodyFatPercent: Double?
    public var screening: DietScreening
    public var pace: AdaptationPace?

    public init(
        sex: EquationSex = .female,
        birthYear: Int = 1995,
        heightCm: Double = 170,
        activity: ActivityLevel = .lowActive,
        goal: DietGoal = .maintenance,
        pattern: DietPattern = .omnivore,
        cuisines: [String] = [],
        trainingLoad: TrainingLoad? = nil,
        bodyFatPercent: Double? = nil,
        screening: DietScreening = DietScreening(),
        pace: AdaptationPace? = nil
    ) {
        self.sex = sex
        self.birthYear = birthYear
        self.heightCm = heightCm
        self.activity = activity
        self.goal = goal
        self.pattern = pattern
        self.cuisines = cuisines
        self.trainingLoad = trainingLoad
        self.bodyFatPercent = bodyFatPercent
        self.screening = screening
        self.pace = pace
    }
}

/// One body-weight measurement, typed by the athlete (``manual``) or read from Apple Health (``appleHealth``). ``utcOffsetSeconds`` is the local offset when it was taken, so the core can keep one reading per local day.
public struct WeighIn: Codable, Equatable, Identifiable {
    public var id: UUID
    public var kg: Double
    public var measuredAt: Date
    public var source: String
    public var timeZone: String
    public var utcOffsetSeconds: Int

    public init(
        id: UUID = UUID(),
        kg: Double,
        measuredAt: Date,
        source: String = "manual",
        timeZone: String = TimeZone.current.identifier,
        utcOffsetSeconds: Int = TimeZone.current.secondsFromGMT()
    ) {
        self.id = id
        self.kg = kg
        self.measuredAt = measuredAt
        self.source = source
        self.timeZone = timeZone
        self.utcOffsetSeconds = utcOffsetSeconds
    }
}

/// Daily targets the athlete accepted. ``basis`` says why: setup, profileChange or adjustment.
public struct DietTargets: Codable, Equatable {
    public var energyKcal: Int
    public var proteinG: Int
    public var carbohydrateG: Int
    public var fatG: Int
    public var fibreG: Int
    public var policyVersion: String
    public var basis: String
    public var setAt: Date

    public init(
        energyKcal: Int,
        proteinG: Int,
        carbohydrateG: Int,
        fatG: Int,
        fibreG: Int,
        policyVersion: String,
        basis: String,
        setAt: Date
    ) {
        self.energyKcal = energyKcal
        self.proteinG = proteinG
        self.carbohydrateG = carbohydrateG
        self.fatG = fatG
        self.fibreG = fibreG
        self.policyVersion = policyVersion
        self.basis = basis
        self.setAt = setAt
    }
}

/// An accepted or rejected diet suggestion, kept as history.
public struct DietDecision: Codable, Equatable, Identifiable {
    public var id: UUID
    public var kind: String
    public var targets: DietTargets
    public var reason: String
    public var decidedAt: Date
    public var status: RecommendationStatus

    public init(
        id: UUID,
        kind: String,
        targets: DietTargets,
        reason: String,
        decidedAt: Date,
        status: RecommendationStatus
    ) {
        self.id = id
        self.kind = kind
        self.targets = targets
        self.reason = reason
        self.decidedAt = decidedAt
        self.status = status
    }
}

/// One major muscle this week: sets logged, sets the accepted week prescribes, and the weekly target.
public struct MuscleRing: Codable, Equatable {
    public var muscle: String
    public var done: Double
    public var planned: Double
    public var target: Double

    public init(
        muscle: String,
        done: Double,
        planned: Double,
        target: Double
    ) {
        self.muscle = muscle
        self.done = done
        self.planned = planned
        self.target = target
    }
}

/// This week's muscle rings from the athlete's local Monday (ADR-020). Counted from logged sets only.
public struct WeekRings: Codable, Equatable {
    public var weekStart: Date
    public var muscles: [MuscleRing]

    public init(
        weekStart: Date,
        muscles: [MuscleRing]
    ) {
        self.weekStart = weekStart
        self.muscles = muscles
    }
}

/// A period the athlete marked as on a break, sick or injured. While active, automatic proposals and plan adaptation pause, and its days do not count as missed (ADR-019).
public struct StatusPeriod: Codable, Equatable, Identifiable {
    public var id: UUID
    public var kind: StatusKind
    public var startedAt: Date
    public var endsAt: Date?
    public var endedAt: Date?

    public init(
        id: UUID,
        kind: StatusKind,
        startedAt: Date,
        endsAt: Date? = nil,
        endedAt: Date? = nil
    ) {
        self.id = id
        self.kind = kind
        self.startedAt = startedAt
        self.endsAt = endsAt
        self.endedAt = endedAt
    }
}

/// Everything the app persists. One file, one athlete.
public struct AthleteState: Codable, Equatable {
    public var schemaVersion: Int
    public var athleteID: UUID
    public var revision: Int
    public var contextRevision: Int
    public var profile: Profile?
    public var program: Program?
    public var nextPlanOverride: SessionPlan?
    public var previousPrograms: [Program]
    public var sessions: [WorkoutSession]
    public var recommendations: [Recommendation]
    public var painExclusions: Set<String>
    public var audits: [AuditEntry]
    public var conflicts: [Conflict]
    public var operations: Set<UUID>
    public var events: [AnalyticsEvent]
    public var meals: [Meal]
    public var mealAudits: [MealAudit]
    public var recipes: [Recipe]
    public var dietProfile: DietProfile?
    public var weighIns: [WeighIn]
    public var dietTargets: DietTargets?
    public var dietDecisions: [DietDecision]
    public var excludedWeighIns: [Date]
    public var statusPeriods: [StatusPeriod]

    public init(
        schemaVersion: Int = 5,
        athleteID: UUID = UUID(),
        revision: Int = 0,
        contextRevision: Int = 0,
        profile: Profile? = nil,
        program: Program? = nil,
        nextPlanOverride: SessionPlan? = nil,
        previousPrograms: [Program] = [],
        sessions: [WorkoutSession] = [],
        recommendations: [Recommendation] = [],
        painExclusions: Set<String> = [],
        audits: [AuditEntry] = [],
        conflicts: [Conflict] = [],
        operations: Set<UUID> = [],
        events: [AnalyticsEvent] = [],
        meals: [Meal] = [],
        mealAudits: [MealAudit] = [],
        recipes: [Recipe] = [],
        dietProfile: DietProfile? = nil,
        weighIns: [WeighIn] = [],
        dietTargets: DietTargets? = nil,
        dietDecisions: [DietDecision] = [],
        excludedWeighIns: [Date] = [],
        statusPeriods: [StatusPeriod] = []
    ) {
        self.schemaVersion = schemaVersion
        self.athleteID = athleteID
        self.revision = revision
        self.contextRevision = contextRevision
        self.profile = profile
        self.program = program
        self.nextPlanOverride = nextPlanOverride
        self.previousPrograms = previousPrograms
        self.sessions = sessions
        self.recommendations = recommendations
        self.painExclusions = painExclusions
        self.audits = audits
        self.conflicts = conflicts
        self.operations = operations
        self.events = events
        self.meals = meals
        self.mealAudits = mealAudits
        self.recipes = recipes
        self.dietProfile = dietProfile
        self.weighIns = weighIns
        self.dietTargets = dietTargets
        self.dietDecisions = dietDecisions
        self.excludedWeighIns = excludedWeighIns
        self.statusPeriods = statusPeriods
    }
}

/// Descriptive record from free-exercise-db. Never a governed Exercise. ``evidence`` is added by ``scripts/annotate_catalog.py`` and absent when no reviewed research covers the exercise.
public struct CatalogExercise: Codable, Equatable, Identifiable {
    public var id: String
    public var name: String
    public var force: String?
    public var level: String
    public var mechanic: String?
    public var equipment: String?
    public var primaryMuscles: [String]
    public var secondaryMuscles: [String]
    public var instructions: [String]
    public var category: String
    public var images: [String]
    public var evidence: [CatalogEvidence]?

    public init(
        id: String,
        name: String,
        force: String?,
        level: String,
        mechanic: String?,
        equipment: String?,
        primaryMuscles: [String],
        secondaryMuscles: [String],
        instructions: [String],
        category: String,
        images: [String],
        evidence: [CatalogEvidence]? = nil
    ) {
        self.id = id
        self.name = name
        self.force = force
        self.level = level
        self.mechanic = mechanic
        self.equipment = equipment
        self.primaryMuscles = primaryMuscles
        self.secondaryMuscles = secondaryMuscles
        self.instructions = instructions
        self.category = category
        self.images = images
        self.evidence = evidence
    }
}

/// What one cited study found about a catalog exercise. Descriptive only: never feeds progression.
public struct CatalogEvidence: Codable, Equatable {
    public var findingID: String
    public var outcome: String
    public var muscles: [String]
    public var result: String
    public var finding: String
    public var certainty: String
    public var design: String
    public var citation: String
    public var locator: String
    public var fullTextRead: Bool
    public var doi: String?
    public var pmid: String?

    public init(
        findingID: String,
        outcome: String,
        muscles: [String],
        result: String,
        finding: String,
        certainty: String,
        design: String,
        citation: String,
        locator: String,
        fullTextRead: Bool,
        doi: String? = nil,
        pmid: String? = nil
    ) {
        self.findingID = findingID
        self.outcome = outcome
        self.muscles = muscles
        self.result = result
        self.finding = finding
        self.certainty = certainty
        self.design = design
        self.citation = citation
        self.locator = locator
        self.fullTextRead = fullTextRead
        self.doi = doi
        self.pmid = pmid
    }
}

/// What Today shows under one slot: a needs-state, a paused state or a kept plan.
public struct SlotStatus: Codable, Equatable {
    public var slotID: UUID
    public var reason: String
    public var tone: String
    public var title: String
    public var body: String
    public var action: String?

    public init(
        slotID: UUID,
        reason: String,
        tone: String,
        title: String,
        body: String,
        action: String? = nil
    ) {
        self.slotID = slotID
        self.reason = reason
        self.tone = tone
        self.title = title
        self.body = body
        self.action = action
    }
}

/// A pending recommendation as Today shows it. Accept and reject still go through state commands.
public struct ProposalCard: Codable, Equatable {
    public var recommendationID: UUID
    public var kind: String
    public var slotID: UUID?
    public var title: String
    public var body: String

    public init(
        recommendationID: UUID,
        kind: String,
        slotID: UUID? = nil,
        title: String,
        body: String
    ) {
        self.recommendationID = recommendationID
        self.kind = kind
        self.slotID = slotID
        self.title = title
        self.body = body
    }
}

/// Read-only Today view model. ``autoRequest`` names one slot whose progression the host may request; ``autoReplan`` says the host may request a week that fits recent attendance (ADR-018).
public struct TodayStatus: Codable, Equatable {
    public var slots: [SlotStatus]
    public var proposals: [ProposalCard]
    public var autoRequest: UUID?
    public var autoReplan: Bool?
    public var status: StatusPeriod?

    public init(
        slots: [SlotStatus] = [],
        proposals: [ProposalCard] = [],
        autoRequest: UUID? = nil,
        autoReplan: Bool? = nil,
        status: StatusPeriod? = nil
    ) {
        self.slots = slots
        self.proposals = proposals
        self.autoRequest = autoRequest
        self.autoReplan = autoReplan
        self.status = status
    }
}

/// One recorded session as logged.
public struct ProgressEntry: Codable, Equatable {
    public var sessionID: UUID
    public var date: Date
    public var summary: String

    public init(
        sessionID: UUID,
        date: Date,
        summary: String
    ) {
        self.sessionID = sessionID
        self.date = date
        self.summary = summary
    }
}

/// Recorded values for one exercise, newest first. Nothing is estimated or projected.
public struct ExerciseProgress: Codable, Equatable {
    public var exerciseID: String
    public var name: String
    public var unit: MassUnit
    public var load: Double?
    public var unchangedSessions: Int
    public var entries: [ProgressEntry]

    public init(
        exerciseID: String,
        name: String,
        unit: MassUnit,
        load: Double? = nil,
        unchangedSessions: Int,
        entries: [ProgressEntry]
    ) {
        self.exerciseID = exerciseID
        self.name = name
        self.unit = unit
        self.load = load
        self.unchangedSessions = unchangedSessions
        self.entries = entries
    }
}

/// The least-squares weight trend over the policy window. Absent until enough weigh-ins exist.
public struct WeightTrend: Codable, Equatable {
    public var latestKg: Double
    public var weeklyChangeKg: Double
    public var weeklyChangeFraction: Double
    public var weighIns: Int
    public var windowDays: Int

    public init(
        latestKg: Double,
        weeklyChangeKg: Double,
        weeklyChangeFraction: Double,
        weighIns: Int,
        windowDays: Int
    ) {
        self.latestKg = latestKg
        self.weeklyChangeKg = weeklyChangeKg
        self.weeklyChangeFraction = weeklyChangeFraction
        self.weighIns = weighIns
        self.windowDays = windowDays
    }
}

/// A suggested change to the daily targets. Inert until the athlete accepts it.
public struct DietAdjustment: Codable, Equatable {
    public var targets: DietTargets
    public var reason: String
    public var title: String
    public var body: String

    public init(
        targets: DietTargets,
        reason: String,
        title: String,
        body: String
    ) {
        self.targets = targets
        self.reason = reason
        self.title = title
        self.body = body
    }
}

/// A household portion from USDA FoodData Central.
public struct FoodPortion: Codable, Equatable {
    public var label: String
    public var grams: Double

    public init(
        label: String,
        grams: Double
    ) {
        self.label = label
        self.grams = grams
    }
}

/// A food that fits what is left of today's targets.
public struct FoodSuggestion: Codable, Equatable {
    public var foodID: Int
    public var name: String
    public var portion: FoodPortion
    public var nutrients: Nutrients
    public var reason: String

    public init(
        foodID: Int,
        name: String,
        portion: FoodPortion,
        nutrients: Nutrients,
        reason: String
    ) {
        self.foodID = foodID
        self.name = name
        self.portion = portion
        self.nutrients = nutrients
        self.reason = reason
    }
}

/// Why a target is what it is: the value and the research behind it.
public struct DietCitation: Codable, Equatable {
    public var parameter: String
    public var value: String
    public var citation: String
    public var locator: String
    public var certainty: String

    public init(
        parameter: String,
        value: String,
        citation: String,
        locator: String,
        certainty: String
    ) {
        self.parameter = parameter
        self.value = value
        self.citation = citation
        self.locator = locator
        self.certainty = certainty
    }
}

/// Read-only Diet tab model. In a preview, ``targets`` is what accepting the profile would set.
public struct DietView: Codable, Equatable {
    public var status: DietStatus
    public var reason: String
    public var message: String
    public var targets: DietTargets?
    public var eaten: Nutrients
    public var remaining: Nutrients?
    public var trend: WeightTrend?
    public var adjustment: DietAdjustment?
    public var suggestions: [FoodSuggestion]
    public var notes: [String]
    public var citations: [DietCitation]
    public var policyVersion: String

    public init(
        status: DietStatus = .needsInput,
        reason: String = "NO_DIET_PROFILE",
        message: String = "",
        targets: DietTargets? = nil,
        eaten: Nutrients = Nutrients(),
        remaining: Nutrients? = nil,
        trend: WeightTrend? = nil,
        adjustment: DietAdjustment? = nil,
        suggestions: [FoodSuggestion] = [],
        notes: [String] = [],
        citations: [DietCitation] = [],
        policyVersion: String = ""
    ) {
        self.status = status
        self.reason = reason
        self.message = message
        self.targets = targets
        self.eaten = eaten
        self.remaining = remaining
        self.trend = trend
        self.adjustment = adjustment
        self.suggestions = suggestions
        self.notes = notes
        self.citations = citations
        self.policyVersion = policyVersion
    }
}

/// Everything the tab screens derive from state, computed in one pass after each change.
public struct CoreViews: Codable, Equatable {
    public var today: TodayStatus
    public var progress: [ExerciseProgress]
    public var diet: DietView
    public var rings: WeekRings?

    public init(
        today: TodayStatus = TodayStatus(),
        progress: [ExerciseProgress] = [],
        diet: DietView = DietView(),
        rings: WeekRings? = nil
    ) {
        self.today = today
        self.progress = progress
        self.diet = diet
        self.rings = rings
    }
}

/// One USDA FoodData Central food for logging (public domain, CC0).
public struct FoodItem: Codable, Equatable, Identifiable {
    public var id: Int
    public var name: String
    public var category: String
    public var per100g: Nutrients
    public var fibre: Double?
    public var portions: [FoodPortion]
    public var patterns: [DietPattern]

    public init(
        id: Int,
        name: String,
        category: String,
        per100g: Nutrients,
        fibre: Double? = nil,
        portions: [FoodPortion],
        patterns: [DietPattern]
    ) {
        self.id = id
        self.name = name
        self.category = category
        self.per100g = per100g
        self.fibre = fibre
        self.portions = portions
        self.patterns = patterns
    }
}

/// One selectable option the setup screen shows.
public struct ChoiceOption: Codable, Equatable, Identifiable {
    public var id: String
    public var title: String
    public var detail: String

    public init(
        id: String,
        title: String,
        detail: String
    ) {
        self.id = id
        self.title = title
        self.detail = detail
    }
}

/// What the diet setup screen offers, taken from the active diet policy.
public struct DietOptions: Codable, Equatable {
    public var activityLevels: [ChoiceOption]
    public var goals: [ChoiceOption]
    public var patterns: [ChoiceOption]
    public var cuisines: [ChoiceOption]
    public var trainingLoads: [ChoiceOption]
    public var exclusions: [ChoiceOption]
    public var scoffQuestions: [String]
    public var minimumAgeYears: Int
    public var paces: [ChoiceOption]
    public var defaultPace: AdaptationPace
    public var paceQuestion: String
    public var paceNote: String
    public var policyVersion: String

    public init(
        activityLevels: [ChoiceOption],
        goals: [ChoiceOption],
        patterns: [ChoiceOption],
        cuisines: [ChoiceOption],
        trainingLoads: [ChoiceOption],
        exclusions: [ChoiceOption],
        scoffQuestions: [String],
        minimumAgeYears: Int,
        paces: [ChoiceOption],
        defaultPace: AdaptationPace,
        paceQuestion: String,
        paceNote: String,
        policyVersion: String
    ) {
        self.activityLevels = activityLevels
        self.goals = goals
        self.patterns = patterns
        self.cuisines = cuisines
        self.trainingLoads = trainingLoads
        self.exclusions = exclusions
        self.scoffQuestions = scoffQuestions
        self.minimumAgeYears = minimumAgeYears
        self.paces = paces
        self.defaultPace = defaultPace
        self.paceQuestion = paceQuestion
        self.paceNote = paceNote
        self.policyVersion = policyVersion
    }
}

/// One session of a weekly option: its day, session type, estimated minutes and working sets.
public struct WeekSession: Codable, Equatable {
    public var weekday: Int
    public var name: String
    public var minutes: Double
    public var exercises: Int
    public var sets: Int

    public init(
        weekday: Int,
        name: String,
        minutes: Double,
        exercises: Int,
        sets: Int
    ) {
        self.weekday = weekday
        self.name = name
        self.minutes = minutes
        self.exercises = exercises
        self.sets = sets
    }
}

/// One week the athlete may choose (ADR-017). ``volume`` is ``full`` or ``reduced`` (time-limited); ``reasons`` are codes the host explains. Choosing it is still a proposal the athlete accepts.
public struct WeekOption: Codable, Equatable, Identifiable {
    public var id: String
    public var split: String
    public var name: String
    public var days: [Int]
    public var sessions: [WeekSession]
    public var sessionsPerWeek: Int
    public var weeklyMinutes: Double
    public var volume: String
    public var score: Double
    public var reasons: [String]

    public init(
        id: String,
        split: String,
        name: String,
        days: [Int],
        sessions: [WeekSession],
        sessionsPerWeek: Int,
        weeklyMinutes: Double,
        volume: String,
        score: Double,
        reasons: [String]
    ) {
        self.id = id
        self.split = split
        self.name = name
        self.days = days
        self.sessions = sessions
        self.sessionsPerWeek = sessionsPerWeek
        self.weeklyMinutes = weeklyMinutes
        self.volume = volume
        self.score = score
        self.reasons = reasons
    }
}

/// What the on-device language model read from the athlete's words. Only a draft: ``readSet`` keeps a number only if the athlete said it.
public struct SpokenSet: Codable, Equatable {
    public var exercise: String?
    public var reps: Int?
    public var load: Double?
    public var rir: Int?

    public init(
        exercise: String? = nil,
        reps: Int? = nil,
        load: Double? = nil,
        rir: Int? = nil
    ) {
        self.exercise = exercise
        self.reps = reps
        self.load = load
        self.rir = rir
    }
}

/// A set ready for the athlete to confirm. Saved only through ``saveSet`` after the athlete taps Save.
public struct SetPreview: Codable, Equatable {
    public var sessionID: UUID
    public var slotID: UUID
    public var exerciseID: String
    public var name: String
    public var index: Int
    public var kind: SetKind
    public var reps: Int
    public var load: Double?
    public var unit: MassUnit
    public var rir: Int?

    public init(
        sessionID: UUID,
        slotID: UUID,
        exerciseID: String,
        name: String,
        index: Int,
        kind: SetKind,
        reps: Int,
        load: Double? = nil,
        unit: MassUnit,
        rir: Int? = nil
    ) {
        self.sessionID = sessionID
        self.slotID = slotID
        self.exerciseID = exerciseID
        self.name = name
        self.index = index
        self.kind = kind
        self.reps = reps
        self.load = load
        self.unit = unit
        self.rir = rir
    }
}

/// A ``preview`` when the set is complete, otherwise a ``question``. ``ignored`` names draft fields dropped because the athlete never said them.
public struct SetReading: Codable, Equatable {
    public var preview: SetPreview?
    public var question: String?
    public var ignored: [String]

    public init(
        preview: SetPreview? = nil,
        question: String? = nil,
        ignored: [String] = []
    ) {
        self.preview = preview
        self.question = question
        self.ignored = ignored
    }
}
