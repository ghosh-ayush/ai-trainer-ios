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

// MARK: - Records

/// What the athlete told us at onboarding. No body metrics, no estimated strength.
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
        preferredExercises: Set<String> = []
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

/// One session's accepted prescriptions. ``modified`` marks a temporary shortened/substituted copy.
public struct SessionPlan: Codable, Equatable, Identifiable {
    public var id: UUID
    public var revision: Int
    public var name: String
    public var slots: [Prescription]
    public var modified: Bool
    public var scheduledDate: Date?
    public var warmUpMinutes: Int

    public init(
        id: UUID = UUID(),
        revision: Int = 1,
        name: String,
        slots: [Prescription],
        modified: Bool = false,
        scheduledDate: Date? = nil,
        warmUpMinutes: Int = 5
    ) {
        self.id = id
        self.revision = revision
        self.name = name
        self.slots = slots
        self.modified = modified
        self.scheduledDate = scheduledDate
        self.warmUpMinutes = warmUpMinutes
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

/// The Training Brain's answer. ``after`` is the proposed plan for ``proposeChange`` outcomes.
public struct Decision: Codable, Equatable {
    public var outcome: DecisionOutcome
    public var reason: String
    public var explanation: String
    public var after: SessionPlan?
    public var evidence: [Evidence]

    public init(
        outcome: DecisionOutcome,
        reason: String,
        explanation: String,
        after: SessionPlan? = nil,
        evidence: [Evidence] = []
    ) {
        self.outcome = outcome
        self.reason = reason
        self.explanation = explanation
        self.after = after
        self.evidence = evidence
    }
}

/// One training request. Which fields are set depends on ``kind``.
public struct TrainingRequest: Codable, Equatable {
    public var kind: String
    public var slotID: UUID?
    public var minutes: Int?
    public var alternativeID: String?
    public var date: Date?

    public init(
        kind: String,
        slotID: UUID? = nil,
        minutes: Int? = nil,
        alternativeID: String? = nil,
        date: Date? = nil
    ) {
        self.kind = kind
        self.slotID = slotID
        self.minutes = minutes
        self.alternativeID = alternativeID
        self.date = date
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

    public init(
        schemaVersion: Int = 2,
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
        recipes: [Recipe] = []
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
    }
}

/// Descriptive record from free-exercise-db. Never a governed Exercise.
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
        images: [String]
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

/// Read-only Today view model. ``autoRequest`` names one slot whose progression the host may request.
public struct TodayStatus: Codable, Equatable {
    public var slots: [SlotStatus]
    public var proposals: [ProposalCard]
    public var autoRequest: UUID?

    public init(
        slots: [SlotStatus] = [],
        proposals: [ProposalCard] = [],
        autoRequest: UUID? = nil
    ) {
        self.slots = slots
        self.proposals = proposals
        self.autoRequest = autoRequest
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

/// Everything the tab screens derive from state, computed in one pass after each change.
public struct CoreViews: Codable, Equatable {
    public var today: TodayStatus
    public var progress: [ExerciseProgress]

    public init(
        today: TodayStatus = TodayStatus(),
        progress: [ExerciseProgress] = []
    ) {
        self.today = today
        self.progress = progress
    }
}
