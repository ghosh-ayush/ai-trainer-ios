import Foundation

/// A presentation snapshot derived from persisted state, suitable for an in-app
/// timer or a future ActivityKit adapter. It never changes the prescription.
public struct WorkoutActivity: Equatable {
    public let sessionID: UUID
    public let completedWorkingSets: Int
    public let restEndsAt: Date?
    public init?(session: WorkoutSession) {
        guard session.active else { return nil }
        sessionID = session.id
        completedWorkingSets = session.completeWorkingSets
        restEndsAt = session.restEndsAt
    }
    /// Deadline-based time survives suspension and relaunch without timer drift.
    /// Pausing the session does not pause elapsed rest (existing behavior).
    public func remainingRestSeconds(at now: Date) -> Int {
        guard let restEndsAt else { return 0 }
        return max(0, Int(ceil(restEndsAt.timeIntervalSince(now))))
    }
}

public enum ThirdPartyNotices {
    public static func text() throws -> String {
        guard let url = Bundle.module.url(forResource: "ThirdPartyNotices", withExtension: "txt") else { throw TrainerError.notFound }
        return try String(contentsOf: url, encoding: .utf8)
    }
}
