import Foundation

/// Policies produce proposals only; TrainingBrain retains eligibility and safety gates.
public protocol ProgressionPolicy {
    func decide(state: AthleteState, plan: SessionPlan, slot: Prescription, policy: TrainingPolicy, now: Date) -> Decision
}

/// Existing fixture rules, extracted without changing decision order or evidence semantics.
public struct DoubleProgressionPolicy: ProgressionPolicy {
    public init() {}
    public func decide(state: AthleteState, plan: SessionPlan, slot: Prescription, policy: TrainingPolicy, now: Date) -> Decision {
        guard !plan.modified else { return .init(.keepPlan, "SESSION_OVERRIDE_ACTIVE", "Finish or discard the temporary session change before progression.") }
        guard slot.equipment.basis == .total || slot.equipment.basis == .perHand else {
            return .init(.unassessed, "LOADING_POLICY_UNAVAILABLE", "Machine settings and assistance need equipment-specific reviewed progression.")
        }
        guard let load = slot.load, load > 0 else { return .init(.needsInput, "BASELINE_REQUIRED", "Confirm a familiar working load. The app does not estimate your strength.") }
        let performance = PerformanceHistory(state: state, slot: slot, now: now)
        let history = performance.sessions
        guard let latest = history.first else { return .init(.keepPlan, "NO_COMPARABLE_HISTORY", "No comparable confirmed performance yet.") }
        if now.timeIntervalSince(latest.startedAt) > Double(policy.historyDays) * 86400 {
            return .init(.needsInput, "HISTORY_STALE", "Reconfirm your baseline before using older performance.")
        }
        let recentLogs = performance.workingLogs(in: latest)
        let evidence = recentLogs.map { Evidence(id: $0.id, revision: $0.revision) }
        if latest.plan.modified { return .init(.keepPlan, "MODIFIED_EXPOSURE", "A shortened or substituted session does not qualify as an original exposure.") }
        if recentLogs.contains(where: \.conflicted) { return .init(.needsInput, "EVIDENCE_CONFLICT", "Resolve the conflicting set before progression.") }
        guard recentLogs.count == slot.workingSets, Set(recentLogs.map(\.index)) == Set(0..<slot.workingSets) else {
            return .init(.keepPlan, "INCOMPLETE_EXPOSURE", "One or more designated working sets are missing; this is not a strength-failure diagnosis.")
        }
        guard recentLogs.allSatisfy({ $0.load == load }) else { return .init(.needsInput, "LOAD_CONTEXT_CHANGED", "The recorded load differs from the planned baseline. Confirm the baseline rather than transferring evidence.") }
        guard recentLogs.allSatisfy({ $0.rir != nil }) else { return .init(.needsInput, "EFFORT_UNKNOWN", "Required effort is unknown. No effort-dependent increase is proposed.") }
        guard recentLogs.allSatisfy({ $0.rir! >= policy.minimumRIR && $0.reps >= slot.lowerReps }) else {
            return .init(.keepPlan, "TARGET_NOT_QUALIFIED", "Repeat or review the plan. The configured rep or effort criterion is not met.")
        }
        var after = plan
        guard let index = after.slots.firstIndex(where: { $0.id == slot.id }) else { return .init(.needsInput, "SLOT_MISSING", "Request a new preview.") }
        if !recentLogs.allSatisfy({ $0.reps >= slot.upperReps }) {
            var targets = recentLogs.map { min($0.reps, slot.upperReps) }
            if let next = targets.firstIndex(where: { $0 < slot.upperReps }) { targets[next] += 1 }
            guard targets != slot.targets else { return .init(.keepPlan, "REPEAT_TARGET", "Keep the current rep targets and load.") }
            after.slots[index].targets = targets
            return .init(.proposeChange, "NEXT_TARGET_REP", "Propose one additional total target rep; load and working-set count stay unchanged.", after: after, evidence: evidence)
        }
        var qualifying: [SetLog] = []
        var previousDate = now
        var count = 0
        for session in history {
            let setLogs = performance.workingLogs(in: session)
            guard !session.plan.modified,
                  now.timeIntervalSince(session.startedAt) <= Double(policy.historyDays) * 86400,
                  previousDate.timeIntervalSince(session.startedAt) <= Double(policy.maximumGapDays) * 86400,
                  setLogs.count == slot.workingSets,
                  Set(setLogs.map(\.index)) == Set(0..<slot.workingSets),
                  setLogs.allSatisfy({ !$0.conflicted && $0.load == load && $0.reps >= slot.upperReps && ($0.rir ?? -1) >= policy.minimumRIR }) else { break }
            count += 1; qualifying += setLogs; previousDate = session.startedAt
            if count >= policy.requiredExposures { break }
        }
        guard count >= policy.requiredExposures else { return .init(.keepPlan, "MORE_EXPOSURES_REQUIRED", "The required consecutive comparable exposures are not complete.") }
        guard let next = slot.equipment.availableLoads.sorted().first(where: { $0 > load + 0.000001 }) else {
            return .init(.needsInput, "EQUIPMENT_STEP_UNKNOWN", "Confirm the available equipment loads. No increment is invented.")
        }
        guard (next - load) / load <= policy.maximumIncreaseFraction + 0.0000001 else {
            return .init(.keepPlan, "INCREMENT_EXCEEDS_BOUND", "The next available load exceeds this policy's permitted change. Keep the load.")
        }
        after.slots[index].load = next
        after.slots[index].targets = Array(repeating: slot.lowerReps, count: slot.workingSets)
        return .init(.proposeChange, "QUALIFYING_EXPOSURES_COMPLETE", "Both qualifying exposures met the rep and reported-effort criteria. Review the next available load; sets do not increase.", after: after,
                     evidence: qualifying.map { Evidence(id: $0.id, revision: $0.revision) })
    }
}
