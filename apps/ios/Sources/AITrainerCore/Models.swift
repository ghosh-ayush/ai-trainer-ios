import Foundation

public enum TrainerError: Error, LocalizedError, Equatable {
    case invalid(String), notFound, conflict, staleProposal, unsupported, corruptStore
    public var errorDescription: String? {
        switch self {
        case .invalid(let message): return message
        case .notFound: return "The requested record no longer exists."
        case .conflict: return "This record changed. Review the conflicting versions before continuing."
        case .staleProposal: return "The evidence or plan changed. Request a fresh preview."
        case .unsupported: return "No enabled, reviewed policy supports this request."
        case .corruptStore: return "Saved data could not be read. It has not been overwritten."
        }
    }
}
public enum Phase: String, Codable, CaseIterable, Identifiable {
    case p0 = "P0", p1 = "P1", p2 = "P2", p3 = "P3", p4 = "P4"
    public var id: String { rawValue }
}
public enum ReviewStatus: String, Codable { case fixture, approved, disabled }
public enum MassUnit: String, Codable, CaseIterable, Identifiable {
    case lb, kg
    public var id: String { rawValue }
    public func convert(_ value: Double, to other: MassUnit) -> Double {
        if self == other { return value }
        return self == .lb ? value * 0.45359237 : value / 0.45359237
    }
}
public enum LoadBasis: String, Codable, CaseIterable {
    case total, perHand, machineSetting, assistance, externalBodyweight
    public var label: String {
        switch self {
        case .total: return "Total load"
        case .perHand: return "Per dumbbell"
        case .machineSetting: return "Machine setting"
        case .assistance: return "Assistance"
        case .externalBodyweight: return "Added external load"
        }
    }
}
public struct Profile: Codable, Equatable {
    public var adultConfirmed = false
    public var supportedScopeConfirmed = false
    public var goal = "Hypertrophy"
    public var experience = "Beginner"
    public var daysPerWeek = 3
    public var minutes = 45
    public var equipment: Set<String> = ["dumbbell"]
    public var preferredUnit: MassUnit = .lb
    public var timeZone = TimeZone.current.identifier
    public var excludedExercises: Set<String> = []
    public var preferredExercises: Set<String> = []
    public init() {}
}
public struct EquipmentContext: Codable, Equatable, Identifiable {
    public var id: String
    public var name: String
    public var kind: String
    public var unit: MassUnit
    public var basis: LoadBasis
    public var availableLoads: [Double]
    public init(id: String, name: String, kind: String, unit: MassUnit, basis: LoadBasis,
                availableLoads: [Double] = []) {
        self.id = id; self.name = name; self.kind = kind; self.unit = unit
        self.basis = basis; self.availableLoads = availableLoads.sorted()
    }
}
public struct Exercise: Codable, Equatable, Identifiable {
    public let id: String
    public let name: String
    public let role: String
    public let equipmentKind: String
    public let basis: LoadBasis
    public let alternatives: [String]
    public let review: ReviewStatus
    public let contentVersion: String
    public init(id: String, name: String, role: String, equipmentKind: String,
                basis: LoadBasis, alternatives: [String], review: ReviewStatus = .fixture) {
        self.id = id; self.name = name; self.role = role; self.equipmentKind = equipmentKind
        self.basis = basis; self.alternatives = alternatives; self.review = review
        self.contentVersion = "fixture-1"
    }
}
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
    public init(id: UUID = UUID(), exerciseID: String, equipment: EquipmentContext,
                load: Double? = nil, optional: Bool = false) {
        self.id = id; self.exerciseID = exerciseID; self.equipment = equipment
        self.protocolID = "DP_TEST_01"; self.workingSets = 3; self.lowerReps = 8
        self.upperReps = 10; self.targets = [8, 8, 8]; self.load = load
        self.restSeconds = 120; self.optional = optional; self.estimatedMinutes = 12
    }
    public var comparisonKey: String {
        [exerciseID, equipment.id, equipment.unit.rawValue, equipment.basis.rawValue,
         protocolID, "bilateral-repetition"].joined(separator: "|")
    }
}
public struct SessionPlan: Codable, Equatable, Identifiable {
    public var id = UUID()
    public var revision = 1
    public var name: String
    public var slots: [Prescription]
    public var modified = false
    public var scheduledDate: Date?
    public var warmUpMinutes = 5
    public var estimatedMinutes: Int { warmUpMinutes + slots.reduce(0) { $0 + $1.estimatedMinutes } }
    public init(name: String, slots: [Prescription]) { self.name = name; self.slots = slots }
}
public struct Program: Codable, Equatable, Identifiable {
    public var id = UUID()
    public var revision = 1
    public var templateID = "FULL_BODY_FIXTURE_01"
    public var libraryVersion = "fixture-1"
    public var plans: [SessionPlan]
    public var sequenceIndex = 0
    public var acceptedAt: Date
    public init(plans: [SessionPlan], acceptedAt: Date) { self.plans = plans; self.acceptedAt = acceptedAt }
    public var nextPlan: SessionPlan? { plans.indices.contains(sequenceIndex) ? plans[sequenceIndex] : nil }
}
public enum SessionStatus: String, Codable { case inProgress, paused, completed, endedEarly, skipped }
public enum SetKind: String, Codable { case working, warmUp, extra }
public enum OmissionReason: String, Codable, CaseIterable { case time, equipment, userChoice, pain, interruption, unspecified }
public struct CheckIn: Codable, Equatable {
    public var energy: String? = nil
    public var soreness: String? = nil
    public var painReported = false
    public var minutes: Int?
    public var unavailableEquipment: Set<String> = []
    public var occurredAt = Date()
    public init() {}
}
public struct SetLog: Codable, Equatable, Identifiable {
    public var id: UUID
    public var operationID: UUID
    public var revision = 1
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
    public var conflicted = false
    public init(id: UUID = UUID(), operationID: UUID = UUID(), prescription: Prescription,
                index: Int, kind: SetKind = .working, load: Double?, reps: Int, rir: Int?,
                occurredAt: Date = Date()) {
        self.id = id; self.operationID = operationID; self.prescriptionID = prescription.id
        self.contextKey = prescription.comparisonKey; self.index = index; self.kind = kind
        self.load = load; self.unit = prescription.equipment.unit; self.basis = prescription.equipment.basis
        self.reps = reps; self.rir = rir; self.occurredAt = occurredAt
    }
    public func validate() throws {
        struct Payload: Encodable { let log: SetLog }
        let _: Bool = try LocalPythonTrainerService.shared.call("validateSet", Payload(log: self))
    }
}
public struct WorkoutSession: Codable, Equatable, Identifiable {
    public var id = UUID()
    public var programID: UUID
    public var programRevision: Int
    public var originalPlan: SessionPlan
    public var plan: SessionPlan
    public var status: SessionStatus = .inProgress
    public var startedAt: Date
    public var endedAt: Date?
    public var timeZone: String
    public var checkIn: CheckIn
    public var logs: [SetLog] = []
    public var omissions: [String: OmissionReason] = [:]
    public var restEndsAt: Date?
    public init(program: Program, plan: SessionPlan, checkIn: CheckIn, now: Date, timeZone: String) {
        self.programID = program.id; self.programRevision = program.revision
        self.originalPlan = plan; self.plan = plan; self.checkIn = checkIn
        self.startedAt = now; self.timeZone = timeZone
    }
    public var active: Bool { status == .inProgress || status == .paused }
    public var completeWorkingSets: Int { logs.filter { $0.kind == .working }.count }
    public func hasWorkingSet(slot: UUID, index: Int) -> Bool {
        logs.contains { $0.prescriptionID == slot && $0.index == index && $0.kind == .working }
    }
}
public enum DecisionOutcome: String, Codable { case keepPlan, proposeChange, needsInput, unassessed, withholdGuidance }
public enum Request: Codable, Equatable {
    case progression(UUID)
    case shorten(Int)
    case substitute(UUID, String)
    case reschedule(Date)
}
public enum RecommendationStatus: String, Codable { case proposed, applied, rejected, expired }
public struct Evidence: Codable, Equatable { public var id: UUID; public var revision: Int }
public struct Decision: Codable, Equatable {
    public var outcome: DecisionOutcome
    public var reason: String
    public var explanation: String
    public var after: SessionPlan?
    public var evidence: [Evidence]
    public init(_ outcome: DecisionOutcome, _ reason: String, _ explanation: String,
                after: SessionPlan? = nil, evidence: [Evidence] = []) {
        self.outcome = outcome; self.reason = reason; self.explanation = explanation
        self.after = after; self.evidence = evidence
    }
}
public struct Recommendation: Codable, Equatable, Identifiable {
    public var id = UUID()
    public var stateRevision: Int
    public var contextRevision: Int
    public var targetPlanID: UUID
    public var targetPlanRevision: Int
    public var request: Request
    public var decision: Decision
    public var policyVersion: String
    public var createdAt: Date
    public var status: RecommendationStatus = .proposed
    public var rejectionReason: String?
}
public struct AuditEntry: Codable, Equatable, Identifiable {
    public var id = UUID()
    public var previous: SetLog
    public var correctedAt: Date
}
public struct Conflict: Codable, Equatable, Identifiable {
    public var id = UUID()
    public var sessionID: UUID
    public var current: SetLog
    public var incoming: SetLog
}
public struct AnalyticsEvent: Codable, Equatable, Identifiable {
    public var id = UUID()
    public var name: String
    public var occurredAt: Date
    public var stateRevision: Int
    public var reason: String?
}
public struct AthleteState: Codable, Equatable {
    public var schemaVersion = 1
    public var athleteID = UUID()
    public var revision = 0
    public var contextRevision = 0
    public var profile: Profile?
    public var program: Program?
    public var nextPlanOverride: SessionPlan?
    public var previousPrograms: [Program] = []
    public var sessions: [WorkoutSession] = []
    public var recommendations: [Recommendation] = []
    public var painExclusions: Set<String> = []
    public var audits: [AuditEntry] = []
    public var conflicts: [Conflict] = []
    public var operations: Set<UUID> = []
    public var events: [AnalyticsEvent] = []
    public var meals: [Meal] = []
    public var mealAudits: [MealAudit] = []
    public var recipes: [Recipe] = []
    public init() {}
    public var activeSession: WorkoutSession? { sessions.last(where: \.active) }
    public var nextPlan: SessionPlan? { nextPlanOverride ?? program?.nextPlan }
    public mutating func expireProposals() {
        for index in recommendations.indices where recommendations[index].status == .proposed {
            recommendations[index].status = .expired
        }
    }
    public mutating func record(_ name: String, now: Date, reason: String? = nil) {
        events.append(AnalyticsEvent(name: name, occurredAt: now, stateRevision: revision + 1, reason: reason))
    }
}
