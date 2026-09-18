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
    public let progressionPolicy: any ProgressionPolicy
    public init(library: ContentLibrary, progressionPolicy: any ProgressionPolicy = DoubleProgressionPolicy()) {
        self.library = library; self.progressionPolicy = progressionPolicy
    }
    public func decide(state: AthleteState, request: Request, now: Date) -> Decision {
        guard let profile = state.profile, profile.adultConfirmed, profile.supportedScopeConfirmed,
              let plan = state.nextPlan else { return .init(.needsInput, "PROFILE_REQUIRED", "Complete a supported profile and accept a plan first.") }
        guard state.activeSession == nil else { return .init(.withholdGuidance, "SESSION_ACTIVE", "The active prescription stays pinned. End the session before changing the next plan.") }
        guard library.enabled(library.policy.review) else { return .init(.withholdGuidance, "POLICY_NOT_APPROVED", "Production guidance needs a reviewed policy bundle.") }
        switch request {
        case .progression(let slotID):
            guard let slot = plan.slots.first(where: { $0.id == slotID }) else { return .init(.needsInput, "SLOT_MISSING", "This exercise slot no longer exists.") }
            if let blocked = block(slot: slot, state: state) { return blocked }
            return progressionPolicy.decide(state: state, plan: plan, slot: slot, policy: library.policy, now: now)
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
}
