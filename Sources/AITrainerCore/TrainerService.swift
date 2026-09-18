import Foundation

public final class TrainerService {
    public let repository: StateRepository
    public let brain: TrainingBrain
    public init(repository: StateRepository, library: ContentLibrary) {
        self.repository = repository; brain = TrainingBrain(library: library)
    }
    public func acceptInitialPlan(profile: Profile, now: Date = Date()) throws {
        let program = try brain.library.initialProgram(profile: profile, now: now)
        try repository.transaction { state in
            guard state.activeSession == nil else { throw TrainerError.invalid("End the active session before changing programs.") }
            if let previous = state.program { state.previousPrograms.append(previous) }
            state.profile = profile; state.program = program; state.nextPlanOverride = nil
            state.contextRevision += 1; state.expireProposals(); state.record("plan_accepted", now: now)
        }
    }
    public func configureLoad(slotID: UUID, load: Double?, options: [Double]) throws {
        guard load == nil || (load!.isFinite && load! >= 0), options.allSatisfy({ $0.isFinite && $0 >= 0 }) else {
            throw TrainerError.invalid("Loads must be finite, nonnegative numbers.")
        }
        try repository.transaction { state in
            guard state.activeSession == nil, var plan = state.nextPlan,
                  let slot = plan.slots.firstIndex(where: { $0.id == slotID }) else { throw TrainerError.conflict }
            plan.slots[slot].load = load
            plan.slots[slot].equipment.availableLoads = Array(Set(options)).sorted()
            plan.revision += 1
            Self.put(plan, in: &state)
            state.contextRevision += 1; state.expireProposals()
        }
    }
    private static func put(_ plan: SessionPlan, in state: inout AthleteState) {
        if plan.modified || state.nextPlanOverride != nil { state.nextPlanOverride = plan }
        else if let index = state.program?.sequenceIndex { state.program?.plans[index] = plan }
    }
    public func start(checkIn: CheckIn = CheckIn(), now: Date = Date()) throws {
        try repository.transaction { state in
            guard state.activeSession == nil else { throw TrainerError.invalid("Resume the existing workout instead of starting a duplicate.") }
            guard let program = state.program, let plan = state.nextPlan, let profile = state.profile else { throw TrainerError.notFound }
            guard !checkIn.painReported else { throw TrainerError.invalid("Pause training guidance and use the reported-concern controls.") }
            guard !plan.slots.contains(where: { state.painExclusions.contains($0.exerciseID) || profile.excludedExercises.contains($0.exerciseID) }) else {
                throw TrainerError.invalid("This plan contains an excluded activity. No replacement is assumed safe.")
            }
            if let minutes = checkIn.minutes, minutes < plan.estimatedMinutes { throw TrainerError.invalid("Preview a shorter session or reschedule before starting.") }
            guard !plan.slots.contains(where: { checkIn.unavailableEquipment.contains($0.equipment.kind) }) else {
                throw TrainerError.invalid("Review an equipment substitution before starting.")
            }
            var session = WorkoutSession(program: program, plan: plan, checkIn: checkIn, now: now, timeZone: profile.timeZone)
            session.originalPlan = program.nextPlan ?? plan
            state.sessions.append(session); state.expireProposals(); state.record("session_started", now: now)
        }
    }
    public func setPaused(_ paused: Bool) throws {
        try repository.transaction { state in
            guard let index = state.sessions.lastIndex(where: \.active) else { throw TrainerError.notFound }
            if !paused, state.sessions[index].plan.slots.contains(where: { state.painExclusions.contains($0.exerciseID) || state.profile?.excludedExercises.contains($0.exerciseID) == true }) {
                throw TrainerError.invalid("Reported concern remains active. End this session; resuming does not establish clearance.")
            }
            state.sessions[index].status = paused ? .paused : .inProgress
        }
    }
    public func saveSet(_ log: SetLog, sessionID: UUID) throws {
        try log.validate()
        try repository.transaction { state in
            if state.operations.contains(log.operationID) {
                guard state.sessions.flatMap(\.logs).contains(log) else { throw TrainerError.invalid("Operation ID was reused with different contents.") }
                return
            }
            guard let index = state.sessions.firstIndex(where: { $0.id == sessionID }),
                  state.sessions[index].status == .inProgress,
                  let slot = state.sessions[index].plan.slots.first(where: { $0.id == log.prescriptionID }),
                  slot.comparisonKey == log.contextKey,
                  slot.equipment.unit == log.unit, slot.equipment.basis == log.basis else { throw TrainerError.conflict }
            if log.kind == .working {
                guard log.index < slot.workingSets,
                      !state.sessions[index].hasWorkingSet(slot: slot.id, index: log.index) else {
                    throw TrainerError.invalid("This working set is already logged. Correct it in History instead.")
                }
            }
            state.sessions[index].logs.append(log)
            state.sessions[index].restEndsAt = log.occurredAt.addingTimeInterval(Double(slot.restSeconds))
            state.operations.insert(log.operationID); state.expireProposals(); state.record("set_saved", now: log.occurredAt)
        }
    }
    public func finish(reason: OmissionReason = .unspecified, now: Date = Date()) throws {
        try repository.transaction { state in
            guard let index = state.sessions.lastIndex(where: \.active) else { throw TrainerError.notFound }
            var session = state.sessions[index]
            for slot in session.plan.slots {
                for set in 0..<slot.workingSets where !session.hasWorkingSet(slot: slot.id, index: set) {
                    session.omissions["\(slot.id.uuidString):\(set)"] = reason
                }
            }
            session.status = session.omissions.isEmpty ? .completed : .endedEarly
            session.endedAt = now; session.restEndsAt = nil
            state.sessions[index] = session
            if let count = state.program?.plans.count, count > 0, let current = state.program?.sequenceIndex {
                state.program?.sequenceIndex = (current + 1) % count
            }
            state.nextPlanOverride = nil; state.expireProposals(); state.record("session_ended", now: now, reason: session.status.rawValue)
        }
    }
    public func skip(now: Date = Date()) throws {
        try repository.transaction { state in
            guard state.activeSession == nil, let program = state.program, let plan = state.nextPlan else { throw TrainerError.conflict }
            var session = WorkoutSession(program: program, plan: plan, checkIn: CheckIn(), now: now, timeZone: state.profile?.timeZone ?? "UTC")
            session.status = .skipped; session.endedAt = now; state.sessions.append(session)
            state.program?.sequenceIndex = (program.sequenceIndex + 1) % program.plans.count
            state.nextPlanOverride = nil; state.expireProposals(); state.record("session_skipped", now: now)
        }
    }
    public func reportPain(exerciseID: String, now: Date = Date()) throws {
        try repository.transaction { state in
            state.painExclusions.insert(exerciseID); state.contextRevision += 1; state.expireProposals()
            if let index = state.sessions.lastIndex(where: \.active) { state.sessions[index].status = .paused }
            state.record("guidance_withheld", now: now, reason: "REPORTED_PAIN")
        }
    }
    public func exclude(exerciseID: String, excluded: Bool) throws {
        try repository.transaction { state in
            guard state.profile != nil else { throw TrainerError.notFound }
            if excluded {
                state.profile?.excludedExercises.insert(exerciseID)
                if let index = state.sessions.lastIndex(where: \.active), state.sessions[index].plan.slots.contains(where: { $0.exerciseID == exerciseID }) { state.sessions[index].status = .paused }
            }
            else { state.profile?.excludedExercises.remove(exerciseID) }
            state.contextRevision += 1; state.expireProposals()
        }
    }
    /// A mismatched revision persists a conflict without selecting the stronger performance.
    @discardableResult public func correctSet(sessionID: UUID, logID: UUID, expectedRevision: Int,
                                             load: Double?, reps: Int, rir: Int?, now: Date = Date()) throws -> Bool {
        try repository.transaction { state in
            guard let si = state.sessions.firstIndex(where: { $0.id == sessionID }),
                  let li = state.sessions[si].logs.firstIndex(where: { $0.id == logID }) else { throw TrainerError.notFound }
            let old = state.sessions[si].logs[li]
            var new = old; new.load = load; new.reps = reps; new.rir = rir
            new.revision = old.revision + 1; new.conflicted = false
            try new.validate()
            state.expireProposals()
            if old.revision != expectedRevision || old.conflicted {
                state.conflicts.append(Conflict(sessionID: sessionID, current: old, incoming: new))
                state.sessions[si].logs[li].conflicted = true
                state.record("sync_conflict", now: now); return false
            }
            state.audits.append(AuditEntry(previous: old, correctedAt: now))
            state.sessions[si].logs[li] = new
            state.record("set_corrected", now: now); return true
        }
    }
    public func resolveConflict(id: UUID, useIncoming: Bool, now: Date = Date()) throws {
        try repository.transaction { state in
            guard let conflict = state.conflicts.first(where: { $0.id == id }),
                  let si = state.sessions.firstIndex(where: { $0.id == conflict.sessionID }),
                  let li = state.sessions[si].logs.firstIndex(where: { $0.id == conflict.current.id }) else { throw TrainerError.notFound }
            let current = state.sessions[si].logs[li]
            var selected = useIncoming ? conflict.incoming : current
            selected.revision = current.revision + 1; selected.conflicted = false
            try selected.validate()
            state.audits.append(AuditEntry(previous: current, correctedAt: now))
            state.sessions[si].logs[li] = selected
            state.conflicts.removeAll { $0.current.id == current.id }
            state.expireProposals(); state.record("conflict_resolved", now: now)
        }
    }
    public func deleteSession(id: UUID) throws {
        try repository.transaction { state in
            guard let session = state.sessions.first(where: { $0.id == id }), !session.active else { throw TrainerError.conflict }
            let ids = Set(session.logs.map(\.id))
            state.sessions.removeAll { $0.id == id }
            state.audits.removeAll { ids.contains($0.previous.id) }
            state.conflicts.removeAll { $0.sessionID == id }
            state.recommendations.removeAll { $0.decision.evidence.contains { ids.contains($0.id) } }
            state.operations.subtract(session.logs.map(\.operationID)); state.expireProposals()
        }
    }
    @discardableResult public func request(_ request: Request, now: Date = Date()) throws -> Decision {
        try repository.transaction { state in
            let decision = brain.decide(state: state, request: request, now: now)
            if decision.outcome == .proposeChange, let plan = state.nextPlan {
                state.expireProposals()
                state.recommendations.append(Recommendation(stateRevision: state.revision, contextRevision: state.contextRevision,
                    targetPlanID: plan.id, targetPlanRevision: plan.revision, request: request, decision: decision,
                    policyVersion: brain.library.policy.version, createdAt: now))
                state.record("recommendation_shown", now: now, reason: decision.reason)
            }
            return decision
        }
    }
    public func acceptRecommendation(id: UUID, now: Date = Date()) throws {
        try repository.transaction { state in
            guard let index = state.recommendations.firstIndex(where: { $0.id == id }) else { throw TrainerError.notFound }
            let rec = state.recommendations[index]
            if rec.status == .applied { return }
            guard rec.status == .proposed, rec.contextRevision == state.contextRevision,
                  rec.policyVersion == brain.library.policy.version, let plan = state.nextPlan,
                  rec.targetPlanID == plan.id, rec.targetPlanRevision == plan.revision,
                  state.activeSession == nil else { throw TrainerError.staleProposal }
            let reevaluated = brain.decide(state: state, request: rec.request, now: now)
            guard reevaluated == rec.decision, var after = reevaluated.after else { throw TrainerError.staleProposal }
            after.revision = plan.revision + 1
            Self.put(after, in: &state)
            state.record("recommendation_accepted", now: now, reason: rec.decision.reason)
            state.expireProposals(); state.recommendations[index].status = .applied
            state.record("recommendation_applied", now: now, reason: rec.decision.reason)
        }
    }
    public func rejectRecommendation(id: UUID, reason: String? = nil, now: Date = Date()) throws {
        try repository.transaction { state in
            guard let index = state.recommendations.firstIndex(where: { $0.id == id }), state.recommendations[index].status == .proposed else { throw TrainerError.staleProposal }
            let allowed = ["equipment_unavailable", "prefer_current", "other"]
            state.recommendations[index].rejectionReason = reason.flatMap { allowed.contains($0) ? $0 : nil }
            state.recommendations[index].status = .rejected
            // Rejection is behavior, not a permanent preference or proof of an outcome.
            state.record("recommendation_rejected", now: now)
        }
    }
    public func deleteMeal(id: UUID) throws {
        try repository.transaction { state in
            state.meals.removeAll { $0.id == id }
            state.mealAudits.removeAll { $0.previous.id == id }
        }
    }
    public func saveMeal(_ meal: Meal, asRecipe: Bool = false) throws {
        try meal.nutrients.validate()
        guard !meal.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { throw TrainerError.invalid("Give this meal a name.") }
        try repository.transaction { state in
            if let index = state.meals.firstIndex(where: { $0.id == meal.id }) {
                guard meal.revision == state.meals[index].revision else { throw TrainerError.conflict }
                state.mealAudits.append(MealAudit(previous: state.meals[index], correctedAt: Date()))
                var edited = meal; edited.revision = state.meals[index].revision + 1; state.meals[index] = edited
            } else { state.meals.append(meal) }
            if asRecipe { state.recipes.append(Recipe(name: meal.name, perServing: meal.nutrients)) }
            state.record("meal_saved", now: meal.occurredAt)
        }
    }
}
