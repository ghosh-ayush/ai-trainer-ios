import Foundation

/// A read-only, deterministically ordered view of comparable completed exposures.
public struct PerformanceHistory {
    public let sessions: [WorkoutSession]
    private let comparisonKey: String
    public init(state: AthleteState, slot: Prescription, now: Date) {
        comparisonKey = slot.comparisonKey
        sessions = state.sessions.filter {
            !$0.active && $0.status != .skipped && $0.startedAt <= now
                && $0.plan.slots.contains { $0.comparisonKey == slot.comparisonKey }
        }.sorted { $0.startedAt == $1.startedAt ? $0.id.uuidString < $1.id.uuidString : $0.startedAt > $1.startedAt }
    }
    public func workingLogs(in session: WorkoutSession) -> [SetLog] {
        session.logs.filter { $0.contextKey == comparisonKey && $0.kind == .working }.sorted { $0.index < $1.index }
    }
}
