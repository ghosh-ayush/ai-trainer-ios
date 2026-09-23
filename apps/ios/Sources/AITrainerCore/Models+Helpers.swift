import Foundation

// Hand-written behaviour on top of the generated records in Models.swift.
// Keep this file free of stored properties: the JSON shape is owned by the contract spec.

// MARK: - Errors and app-only enums

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

/// The persisted shape of a training request inside a Recommendation
/// (Swift's synthesized enum encoding: `{"progression": {"_0": "<uuid>"}}`).
public enum Request: Codable, Equatable {
    case progression(UUID)
    case shorten(Int)
    case substitute(UUID, String)
    case reschedule(Date)
}

// MARK: - Enum presentation helpers

extension MassUnit: Identifiable {
    public var id: String { rawValue }
    public func convert(_ value: Double, to other: MassUnit) -> Double {
        if self == other { return value }
        return self == .lb ? value * 0.45359237 : value / 0.45359237
    }
}

extension LoadBasis {
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

// MARK: - Prescriptions and plans

extension Prescription {
    /// Identity used to compare performance across sessions. Must match `athlete_state.comparison_key` in Python.
    public var comparisonKey: String {
        [exerciseID, equipment.id, equipment.unit.rawValue, equipment.basis.rawValue, protocolID, "bilateral-repetition"]
            .joined(separator: "|")
    }

    /// The DP_TEST_01 development fixture (3 x 8-10, 120 s rest). Test data only — never a production default.
    public static func developmentFixture(
        id: UUID = UUID(), exerciseID: String, equipment: EquipmentContext, load: Double? = nil, optional: Bool = false
    ) -> Prescription {
        Prescription(
            id: id, exerciseID: exerciseID, equipment: equipment, protocolID: "DP_TEST_01",
            workingSets: 3, lowerReps: 8, upperReps: 10, targets: [8, 8, 8], load: load,
            restSeconds: 120, optional: optional, estimatedMinutes: 12
        )
    }
}

extension SessionPlan {
    public var estimatedMinutes: Int { warmUpMinutes + slots.reduce(0) { $0 + $1.estimatedMinutes } }
}

extension Program {
    public var nextPlan: SessionPlan? { plans.indices.contains(sequenceIndex) ? plans[sequenceIndex] : nil }
}

extension TrainingPolicy {
    /// The DP_TEST_01 development fixture policy. Test data only — never a production default.
    public static let developmentFixture = TrainingPolicy(
        id: "DP_TEST_01", version: "fixture-1", review: .fixture, requiredExposures: 2, minimumRIR: 2,
        maximumIncreaseFraction: 0.05, historyDays: 28, maximumGapDays: 14
    )
}

// MARK: - Sessions and set logs

extension SetLog {
    /// A set recorded against a prescription; context, unit and basis are copied from the slot.
    public init(
        id: UUID = UUID(), operationID: UUID = UUID(), prescription: Prescription, index: Int, kind: SetKind = .working,
        load: Double?, reps: Int, rir: Int?, occurredAt: Date = Date()
    ) {
        self.init(
            id: id, operationID: operationID, revision: 1, prescriptionID: prescription.id,
            contextKey: prescription.comparisonKey, index: index, kind: kind, load: load,
            unit: prescription.equipment.unit, basis: prescription.equipment.basis, reps: reps, rir: rir,
            occurredAt: occurredAt, conflicted: false
        )
    }

    public func validate() throws {
        struct Payload: Encodable { let log: SetLog }
        let _: Bool = try LocalPythonTrainerService.shared.call("validateSet", Payload(log: self))
    }
}

extension WorkoutSession {
    public init(program: Program, plan: SessionPlan, checkIn: CheckIn, now: Date, timeZone: String) {
        self.init(
            programID: program.id, programRevision: program.revision, originalPlan: plan, plan: plan,
            startedAt: now, timeZone: timeZone, checkIn: checkIn
        )
    }
    public var active: Bool { status == .inProgress || status == .paused }
    public var completeWorkingSets: Int { logs.filter { $0.kind == .working }.count }
    public func hasWorkingSet(slot: UUID, index: Int) -> Bool {
        logs.contains { $0.prescriptionID == slot && $0.index == index && $0.kind == .working }
    }
}

// MARK: - Decisions

extension Decision {
    public init(_ outcome: DecisionOutcome, _ reason: String, _ explanation: String, after: SessionPlan? = nil, evidence: [Evidence] = []) {
        self.init(outcome: outcome, reason: reason, explanation: explanation, after: after, evidence: evidence)
    }
}

// MARK: - Athlete state

extension AthleteState {
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
