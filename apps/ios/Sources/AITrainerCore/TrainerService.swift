import Foundation

/// The only object feature code talks to. Every mutation is one Python state command:
/// the core computes the candidate state, the repository saves it atomically, and only then
/// does the new snapshot become visible. Nothing here reaches for a global.
public final class TrainerService {
    public let repository: StateRepository
    public let library: ContentLibrary
    public let core: LocalPythonTrainerService
    public init(repository: StateRepository, library: ContentLibrary, core: LocalPythonTrainerService) {
        self.repository = repository; self.library = library; self.core = core
    }

    /// Union of every command's arguments; unset fields are omitted from the JSON.
    private struct Arguments: Encodable {
        var profile: Profile?; var slotID: UUID?; var load: Double?; var options: [Double]?
        var checkIn: CheckIn?; var paused: Bool?; var sessionID: UUID?; var index: Int?; var kind: SetKind?
        var reps: Int?; var rir: Int?; var logID: UUID?; var operationID: UUID?; var reason: String?
        var exerciseID: String?; var excluded: Bool?; var expectedRevision: Int?; var id: UUID?
        var useIncoming: Bool?; var meal: Meal?; var asRecipe: Bool?; var request: TrainingRequest?
    }
    private struct Payload: Encodable {
        let command: String; let state: AthleteState; let arguments: Arguments
        let permitsFixtures: Bool; let now: Date; let ids: [UUID]
    }
    private struct Result: Decodable { let state: AthleteState; let value: Bool?; let decision: Decision? }

    @discardableResult private func command(_ name: String, _ arguments: Arguments = Arguments(), now: Date = Date()) throws -> Result {
        try repository.transaction { state in
            let result: Result = try core.call("stateCommand", Payload(command: name, state: state, arguments: arguments,
                permitsFixtures: library.permitsFixtures, now: now, ids: (0..<10).map { _ in UUID() }))
            state = result.state
            return result
        }
    }

    // MARK: Plan
    public func previewInitialPlan(profile: Profile, now: Date = Date()) throws -> Program {
        struct Preview: Encodable { let profile: Profile; let permitsFixtures: Bool; let now: Date; let ids: [UUID] }
        return try core.call("initialProgram", Preview(profile: profile, permitsFixtures: library.permitsFixtures,
                                                      now: now, ids: (0..<6).map { _ in UUID() }))
    }
    public func acceptInitialPlan(profile: Profile, now: Date = Date()) throws {
        try command("acceptInitialPlan", Arguments(profile: profile), now: now)
    }
    public func configureLoad(slotID: UUID, load: Double?, options: [Double]) throws {
        try command("configureLoad", Arguments(slotID: slotID, load: load, options: options))
    }

    // MARK: Workout
    public func start(checkIn: CheckIn = CheckIn(), now: Date = Date()) throws {
        try command("start", Arguments(checkIn: checkIn), now: now)
    }
    public func skip(now: Date = Date()) throws {
        var checkIn = CheckIn(); checkIn.occurredAt = now
        try command("skip", Arguments(checkIn: checkIn), now: now)
    }
    public func setPaused(_ paused: Bool) throws { try command("setPaused", Arguments(paused: paused)) }
    /// Records what the athlete entered; Python copies the slot's context, unit and basis.
    /// Reuse the same `operationID` when retrying so a repeated save stays one set.
    public func saveSet(sessionID: UUID, slotID: UUID, index: Int, kind: SetKind = .working, load: Double?, reps: Int,
                        rir: Int?, logID: UUID = UUID(), operationID: UUID = UUID(), now: Date = Date()) throws {
        try command("saveSet", Arguments(slotID: slotID, load: load, sessionID: sessionID, index: index, kind: kind,
            reps: reps, rir: rir, logID: logID, operationID: operationID), now: now)
    }
    public func finish(reason: OmissionReason = .unspecified, now: Date = Date()) throws {
        try command("finish", Arguments(reason: reason.rawValue), now: now)
    }
    public func reportPain(exerciseID: String, now: Date = Date()) throws {
        try command("reportPain", Arguments(exerciseID: exerciseID), now: now)
    }
    public func exclude(exerciseID: String, excluded: Bool) throws {
        try command("exclude", Arguments(exerciseID: exerciseID, excluded: excluded))
    }

    // MARK: Records
    /// Returns `false` when the edit raced another one and was kept as a conflict instead.
    @discardableResult public func correctSet(sessionID: UUID, logID: UUID, expectedRevision: Int,
                                             load: Double?, reps: Int, rir: Int?, now: Date = Date()) throws -> Bool {
        try command("correctSet", Arguments(load: load, sessionID: sessionID, reps: reps, rir: rir, logID: logID,
            expectedRevision: expectedRevision), now: now).value ?? false
    }
    public func resolveConflict(id: UUID, useIncoming: Bool, now: Date = Date()) throws {
        try command("resolveConflict", Arguments(id: id, useIncoming: useIncoming), now: now)
    }
    public func deleteSession(id: UUID) throws { try command("deleteSession", Arguments(id: id)) }

    // MARK: Recommendations
    /// Asks the Training Brain; a `proposeChange` answer is stored as a pending recommendation.
    @discardableResult public func request(_ request: TrainingRequest, now: Date = Date()) throws -> Decision {
        guard let decision = try command("requestChange", Arguments(request: request), now: now).decision else {
            throw TrainerError.invalid("Missing decision.")
        }
        return decision
    }
    public func acceptRecommendation(id: UUID, now: Date = Date()) throws {
        try command("acceptRecommendation", Arguments(id: id), now: now)
    }
    public func rejectRecommendation(id: UUID, reason: String? = nil, now: Date = Date()) throws {
        try command("rejectRecommendation", Arguments(reason: reason, id: id), now: now)
    }

    // MARK: Read-only views computed by the core

    private struct StatePayload: Encodable { let state: AthleteState; let permitsFixtures: Bool; let now: Date }
    /// Today's slot cards, pending proposal titles and the one slot (if any) to auto-request.
    public func todayStatus(now: Date = Date()) throws -> TodayStatus {
        try core.call("todayStatus", StatePayload(state: repository.snapshot, permitsFixtures: library.permitsFixtures, now: now))
    }
    /// Recorded values per exercise in the next plan, newest first.
    public func progress(now: Date = Date()) throws -> [ExerciseProgress] {
        try core.call("progress", StatePayload(state: repository.snapshot, permitsFixtures: library.permitsFixtures, now: now))
    }
    /// Available loads around a confirmed working load, in the athlete's own equipment step.
    public func loadSteps(base: Double, step: Double) throws -> [Double] {
        struct Steps: Encodable { let base: Double; let step: Double }
        return try core.call("loadSteps", Steps(base: base, step: step))
    }

    // MARK: Nutrition
    public func saveMeal(_ meal: Meal, asRecipe: Bool = false) throws {
        try command("saveMeal", Arguments(meal: meal, asRecipe: asRecipe))
    }
    public func deleteMeal(id: UUID) throws { try command("deleteMeal", Arguments(id: id)) }
    public func scaleNutrients(_ nutrients: Nutrients, servings: Double) throws -> Nutrients {
        struct Scale: Encodable { let nutrients: Nutrients; let servings: Double }
        return try core.call("nutrients", Scale(nutrients: nutrients, servings: servings))
    }
}
