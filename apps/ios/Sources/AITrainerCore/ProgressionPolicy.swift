import Foundation

/// Compatibility surface; the governed double-progression implementation lives in Python.
public protocol ProgressionPolicy {
    func decide(state: AthleteState, plan: SessionPlan, slot: Prescription, policy: TrainingPolicy, now: Date) -> Decision
}
public struct DoubleProgressionPolicy: ProgressionPolicy {
    public init() {}
    public func decide(state: AthleteState, plan: SessionPlan, slot: Prescription, policy: TrainingPolicy, now: Date) -> Decision {
        do { return try LocalPythonTrainerService.shared.progression(state: state, plan: plan, slot: slot, policy: policy, now: now) }
        catch { return .init(.withholdGuidance, "LOCAL_CORE_UNAVAILABLE", "Local training rules could not run. No change was applied.") }
    }
}
