import Foundation

/// No fixture value in this file is an approved real-world training prescription.
public struct TrainingPolicy: Codable, Equatable {
    public var id = "DP_TEST_01"
    public var version = "fixture-1"
    public var review: ReviewStatus = .fixture
    public var requiredExposures = 2
    public var minimumRIR = 2
    public var maximumIncreaseFraction = 0.05
    public var historyDays = 28
    public var maximumGapDays = 14
    public init() {}
}
public struct ContentLibrary {
    public let exercises: [Exercise]
    public let policy: TrainingPolicy
    public let permitsFixtures: Bool
    public init(permitsFixtures: Bool = false, exercises: [Exercise] = ContentLibrary.fixtureExercises,
                policy: TrainingPolicy = TrainingPolicy()) {
        self.permitsFixtures = permitsFixtures; self.exercises = exercises; self.policy = policy
    }
    public func exercise(_ id: String) -> Exercise? { exercises.first { $0.id == id } }
    public func enabled(_ status: ReviewStatus) -> Bool {
        status == .approved || (status == .fixture && permitsFixtures)
    }
    public static let fixtureExercises: [Exercise] = [
        .init(id: "db_floor_press", name: "Dumbbell floor press", role: "press", equipmentKind: "dumbbell", basis: .perHand, alternatives: ["machine_press", "bench"]),
        .init(id: "bench", name: "Barbell bench press", role: "press", equipmentKind: "barbell", basis: .total, alternatives: ["machine_press", "db_floor_press"]),
        .init(id: "machine_press", name: "Chest press machine", role: "press", equipmentKind: "machine", basis: .machineSetting, alternatives: ["db_floor_press"]),
        .init(id: "db_row", name: "Two-dumbbell row", role: "pull", equipmentKind: "dumbbell", basis: .perHand, alternatives: ["cable_row"]),
        .init(id: "cable_row", name: "Seated cable row", role: "pull", equipmentKind: "machine", basis: .machineSetting, alternatives: ["db_row"]),
        .init(id: "goblet_squat", name: "Goblet squat", role: "squat", equipmentKind: "dumbbell", basis: .total, alternatives: ["leg_press"]),
        .init(id: "leg_press", name: "Leg press", role: "squat", equipmentKind: "machine", basis: .machineSetting, alternatives: ["goblet_squat"]),
        .init(id: "db_curl", name: "Bilateral dumbbell curl", role: "accessory", equipmentKind: "dumbbell", basis: .perHand, alternatives: [])
    ]
    public func initialProgram(profile: Profile, now: Date) throws -> Program {
        guard permitsFixtures, enabled(policy.review) else { throw TrainerError.unsupported }
        guard profile.adultConfirmed, profile.supportedScopeConfirmed,
              ["Hypertrophy", "Strength"].contains(profile.goal),
              (2...4).contains(profile.daysPerWeek), profile.minutes >= 41 else {
            throw TrainerError.invalid("This fixture covers adults, strength/hypertrophy, 2-4 days, and sessions of at least 41 minutes.")
        }
        var slots: [Prescription] = []
        for role in ["press", "pull", "squat"] {
            let eligible = exercises.filter {
                $0.role == role && enabled($0.review) && profile.equipment.contains($0.equipmentKind)
                    && !profile.excludedExercises.contains($0.id)
            }.sorted {
                let a = profile.preferredExercises.contains($0.id), b = profile.preferredExercises.contains($1.id)
                return a == b ? $0.id < $1.id : a
            }
            guard let exercise = eligible.first else { throw TrainerError.unsupported }
            slots.append(Prescription(exerciseID: exercise.id, equipment: context(for: exercise, unit: profile.preferredUnit)))
        }
        if profile.minutes >= 53, profile.equipment.contains("dumbbell"),
           !profile.excludedExercises.contains("db_curl"), let curl = exercise("db_curl") {
            slots.append(Prescription(exerciseID: curl.id, equipment: context(for: curl, unit: profile.preferredUnit), optional: true))
        }
        // One repeating session is deliberate: broader reviewed splits are not supplied yet.
        return Program(plans: [SessionPlan(name: "Full body - development fixture", slots: slots)], acceptedAt: now)
    }
    public func context(for exercise: Exercise, unit: MassUnit) -> EquipmentContext {
        .init(id: "local-\(exercise.id)", name: "My \(exercise.name) equipment", kind: exercise.equipmentKind,
              unit: unit, basis: exercise.basis)
    }
}

public struct TrainingBrain {
    public let library: ContentLibrary
    public init(library: ContentLibrary) { self.library = library }
    public func decide(state: AthleteState, request: Request, now: Date) -> Decision {
        guard let profile = state.profile, profile.adultConfirmed, profile.supportedScopeConfirmed,
              let plan = state.nextPlan else { return .init(.needsInput, "PROFILE_REQUIRED", "Complete a supported profile and accept a plan first.") }
        guard state.activeSession == nil else { return .init(.withholdGuidance, "SESSION_ACTIVE", "The active prescription stays pinned. End the session before changing the next plan.") }
        guard library.enabled(library.policy.review) else { return .init(.withholdGuidance, "POLICY_NOT_APPROVED", "Production guidance needs a reviewed policy bundle.") }
        switch request {
        case .progression(let slotID):
            guard let slot = plan.slots.first(where: { $0.id == slotID }) else { return .init(.needsInput, "SLOT_MISSING", "This exercise slot no longer exists.") }
            if let blocked = block(slot: slot, state: state) { return blocked }
            return progression(state: state, plan: plan, slot: slot, now: now)
        case .shorten(let minutes):
            guard minutes > 0 else { return .init(.needsInput, "TIME_REQUIRED", "Enter available minutes.") }
            var after = plan
            while after.estimatedMinutes > minutes, let index = after.slots.lastIndex(where: \.optional) { after.slots.remove(at: index) }
            guard after.estimatedMinutes <= minutes else { return .init(.needsInput, "REQUIRED_WORK_DOES_NOT_FIT", "Required work does not fit this fixture. Reschedule; rest and warm-up are not compressed.") }
            guard after.slots != plan.slots else { return .init(.keepPlan, "ALREADY_FITS", "The existing session fits the time budget.") }
            after.modified = true
            return .init(.proposeChange, "OPTIONAL_WORK_REMOVED", "Omit optional work for this session only. Rest and warm-up remain unchanged.", after: after)
        case .substitute(let slotID, let alternativeID):
            guard let index = plan.slots.firstIndex(where: { $0.id == slotID }),
                  let original = library.exercise(plan.slots[index].exerciseID),
                  original.alternatives.contains(alternativeID), let alt = library.exercise(alternativeID),
                  library.enabled(alt.review), profile.equipment.contains(alt.equipmentKind),
                  !profile.excludedExercises.contains(alt.id), !state.painExclusions.contains(alt.id) else {
                return .init(.withholdGuidance, "NO_ELIGIBLE_SUBSTITUTE", "No enabled directional substitute matches your equipment and exclusions.")
            }
            if let blocked = block(slot: plan.slots[index], state: state) { return blocked }
            var after = plan
            after.slots[index].exerciseID = alt.id
            after.slots[index].equipment = library.context(for: alt, unit: profile.preferredUnit)
            // Never transfer load between equipment identities, even in the same role.
            after.slots[index].load = nil
            after.modified = true
            return .init(.proposeChange, "CURATED_SUBSTITUTION", "Use \(alt.name) for this session only. Confirm its own load and equipment; the original load is not transferred.", after: after)
        case .reschedule(let date):
            guard date >= now else { return .init(.needsInput, "DATE_IN_PAST", "Choose a future placement.") }
            var after = plan; after.scheduledDate = date
            return .init(.proposeChange, "USER_RESCHEDULE", "Move this session without doubling work or changing the sequence.", after: after)
        }
    }
    private func block(slot: Prescription, state: AthleteState) -> Decision? {
        if state.painExclusions.contains(slot.exerciseID) {
            return .init(.withholdGuidance, "REPORTED_PAIN", "Guidance for this activity is paused because you reported pain. A different exercise is not assumed safe.")
        }
        if state.profile?.excludedExercises.contains(slot.exerciseID) == true {
            return .init(.withholdGuidance, "EXERCISE_EXCLUDED", "Your explicit exclusion takes priority over progression or preferences.")
        }
        guard let exercise = library.exercise(slot.exerciseID), library.enabled(exercise.review) else {
            return .init(.withholdGuidance, "UNREVIEWED_EXERCISE", "This exercise has no enabled guidance policy.")
        }
        return nil
    }
    private func progression(state: AthleteState, plan: SessionPlan, slot: Prescription, now: Date) -> Decision {
        let policy = library.policy
        guard !plan.modified else { return .init(.keepPlan, "SESSION_OVERRIDE_ACTIVE", "Finish or discard the temporary session change before progression.") }
        guard slot.equipment.basis == .total || slot.equipment.basis == .perHand else {
            return .init(.unassessed, "LOADING_POLICY_UNAVAILABLE", "Machine settings and assistance need equipment-specific reviewed progression.")
        }
        guard let load = slot.load, load > 0 else { return .init(.needsInput, "BASELINE_REQUIRED", "Confirm a familiar working load. The app does not estimate your strength.") }
        let history = state.sessions.filter {
            !$0.active && $0.status != .skipped && $0.startedAt <= now
                && $0.plan.slots.contains { $0.comparisonKey == slot.comparisonKey }
        }.sorted { $0.startedAt == $1.startedAt ? $0.id.uuidString < $1.id.uuidString : $0.startedAt > $1.startedAt }
        guard let latest = history.first else { return .init(.keepPlan, "NO_COMPARABLE_HISTORY", "No comparable confirmed performance yet.") }
        if now.timeIntervalSince(latest.startedAt) > Double(policy.historyDays) * 86400 {
            return .init(.needsInput, "HISTORY_STALE", "Reconfirm your baseline before using older performance.")
        }
        func logs(_ session: WorkoutSession) -> [SetLog] {
            session.logs.filter { $0.contextKey == slot.comparisonKey && $0.kind == .working }.sorted { $0.index < $1.index }
        }
        let recentLogs = logs(latest)
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
            let setLogs = logs(session)
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
