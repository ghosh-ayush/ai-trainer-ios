import Foundation

/// Native persistence orchestration. All mutations are computed by the domain service,
/// then saved atomically before the new snapshot becomes visible to feature code.
///
/// This is the only object feature code talks to. It owns the content library, the state
/// repository and the domain core it was composed with; nothing here reaches for a global.
public final class TrainerService {
    public let repository: StateRepository
    public let library: ContentLibrary
    public let core: any TrainerDomainService
    public init(repository: StateRepository, library: ContentLibrary, core: any TrainerDomainService) {
        self.repository = repository; self.library = library; self.core = core
    }
    private struct Arguments: Encodable {
        var profile: Profile?; var slotID: UUID?; var load: Double?; var options: [Double]?
        var checkIn: CheckIn?; var paused: Bool?; var log: SetLog?; var sessionID: UUID?
        var reason: OmissionReason?; var exerciseID: String?; var excluded: Bool?
        var logID: UUID?; var expectedRevision: Int?; var reps: Int?; var rir: Int?
        var id: UUID?; var useIncoming: Bool?; var meal: Meal?; var asRecipe: Bool?
    }
    private struct Payload: Encodable {
        let command: String; let state: AthleteState; let arguments: Arguments
        let library: LibraryDTO; let now: Date; let ids: [UUID]
    }
    private struct Result: Decodable { let state: AthleteState; let value: Bool? }
    @discardableResult private func command(_ name: String, _ arguments: Arguments = Arguments(), now: Date = Date()) throws -> Bool? {
        try repository.transaction { state in
            let result: Result = try core.call("stateCommand", Payload(command: name, state: state, arguments: arguments,
                library: LibraryDTO(library), now: now, ids: (0..<10).map { _ in UUID() }))
            state = result.state; return result.value
        }
    }
    public func previewInitialPlan(profile: Profile, now: Date = Date()) throws -> Program {
        try core.initialProgram(profile: profile, library: library, now: now)
    }
    public func scaleNutrients(_ nutrients: Nutrients, servings: Double) throws -> Nutrients {
        try core.nutrients(nutrients, servings: servings)
    }
    public func acceptInitialPlan(profile: Profile, now: Date = Date()) throws {
        try command("acceptInitialPlan", Arguments(profile: profile), now: now)
    }
    public func configureLoad(slotID: UUID, load: Double?, options: [Double]) throws {
        try command("configureLoad", Arguments(slotID: slotID, load: load, options: options))
    }
    public func start(checkIn: CheckIn = CheckIn(), now: Date = Date()) throws {
        try command("start", Arguments(checkIn: checkIn), now: now)
    }
    public func setPaused(_ paused: Bool) throws { try command("setPaused", Arguments(paused: paused)) }
    public func saveSet(_ log: SetLog, sessionID: UUID) throws {
        try command("saveSet", Arguments(log: log, sessionID: sessionID), now: log.occurredAt)
    }
    public func finish(reason: OmissionReason = .unspecified, now: Date = Date()) throws {
        try command("finish", Arguments(reason: reason), now: now)
    }
    public func skip(now: Date = Date()) throws {
        var checkIn = CheckIn(); checkIn.occurredAt = now
        try command("skip", Arguments(checkIn: checkIn), now: now)
    }
    public func reportPain(exerciseID: String, now: Date = Date()) throws {
        try command("reportPain", Arguments(exerciseID: exerciseID), now: now)
    }
    public func exclude(exerciseID: String, excluded: Bool) throws {
        try command("exclude", Arguments(exerciseID: exerciseID, excluded: excluded))
    }
    @discardableResult public func correctSet(sessionID: UUID, logID: UUID, expectedRevision: Int,
                                             load: Double?, reps: Int, rir: Int?, now: Date = Date()) throws -> Bool {
        try command("correctSet", Arguments(load: load, sessionID: sessionID, logID: logID,
            expectedRevision: expectedRevision, reps: reps, rir: rir), now: now) ?? false
    }
    public func resolveConflict(id: UUID, useIncoming: Bool, now: Date = Date()) throws {
        try command("resolveConflict", Arguments(id: id, useIncoming: useIncoming), now: now)
    }
    public func deleteSession(id: UUID) throws { try command("deleteSession", Arguments(id: id)) }
    @discardableResult public func request(_ request: Request, now: Date = Date()) throws -> Decision {
        try repository.transaction { state in
            let result = try core.recommendation("request", state: state, request: request, library: library, now: now)
            guard let decision = result.decision else { throw TrainerError.invalid("Missing decision.") }
            state = result.state; return decision
        }
    }
    public func acceptRecommendation(id: UUID, now: Date = Date()) throws {
        try repository.transaction { state in
            state = try core.recommendation("accept", state: state, id: id, library: library, now: now).state
        }
    }
    public func rejectRecommendation(id: UUID, reason: String? = nil, now: Date = Date()) throws {
        try repository.transaction { state in
            state = try core.recommendation("reject", state: state, id: id, reason: reason, library: library, now: now).state
        }
    }
    public func deleteMeal(id: UUID) throws { try command("deleteMeal", Arguments(id: id)) }
    public func saveMeal(_ meal: Meal, asRecipe: Bool = false) throws {
        try command("saveMeal", Arguments(meal: meal, asRecipe: asRecipe))
    }
}
