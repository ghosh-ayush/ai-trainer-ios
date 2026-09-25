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
        var optionID: String?
        var status: StatusKind?
        var endsAt: Date?
    }
    private struct Payload<CommandArguments: Encodable>: Encodable {
        let command: String; let state: AthleteState; let arguments: CommandArguments
        let permitsFixtures: Bool; let now: Date; let ids: [UUID]
    }
    private struct Result: Decodable { let state: AthleteState; let value: Bool?; let decision: Decision? }

    @discardableResult private func command<CommandArguments: Encodable>(_ name: String, _ arguments: CommandArguments,
                                                                        now: Date = Date(), idCount: Int = 10) throws -> Result {
        try repository.transaction { state in
            let result: Result = try core.call("stateCommand", Payload(command: name, state: state, arguments: arguments,
                permitsFixtures: library.permitsFixtures, now: now, ids: (0..<idCount).map { _ in UUID() }))
            state = result.state
            return result
        }
    }
    @discardableResult private func command(_ name: String, now: Date = Date()) throws -> Result {
        try command(name, Arguments(), now: now)
    }

    // MARK: Plan
    /// Ids a weekly program (ADR-017) may need: the program, then one per plan and slot, plus events.
    static let programIDCount = 80

    /// Up to three genuinely different weeks for the athlete's free days and minutes, best first.
    /// Empty when the active content has no weekly planner (it then builds one repeating session).
    public func weekOptions(profile: Profile) throws -> [WeekOption] {
        struct Options: Encodable { let profile: Profile; let permitsFixtures: Bool }
        return try core.call("weekOptions", Options(profile: profile, permitsFixtures: library.permitsFixtures))
    }
    /// What accepting would create. `optionID` names a week from `weekOptions`; `nil` takes the best one.
    public func previewInitialPlan(profile: Profile, optionID: String? = nil, now: Date = Date()) throws -> Program {
        struct Preview: Encodable {
            let profile: Profile
            let permitsFixtures: Bool
            let now: Date
            let ids: [UUID]
            let optionID: String?
        }
        return try core.call("initialProgram", Preview(profile: profile, permitsFixtures: library.permitsFixtures, now: now,
                                                      ids: (0..<Self.programIDCount).map { _ in UUID() }, optionID: optionID))
    }
    /// The core rebuilds the week from the same inputs and refuses an option that no longer fits.
    public func acceptInitialPlan(profile: Profile, optionID: String? = nil, now: Date = Date()) throws {
        try command("acceptInitialPlan", Arguments(profile: profile, optionID: optionID), now: now, idCount: Self.programIDCount)
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

    // MARK: Status (ADR-019)
    /// Marks a break, illness or injury. Automatic proposals pause and its days never count as missed.
    public func setStatus(_ status: StatusKind, endsAt: Date? = nil, now: Date = Date()) throws {
        try command("setStatus", Arguments(status: status, endsAt: endsAt), now: now)
    }
    /// "I'm back": ends the active status now.
    public func endStatus(now: Date = Date()) throws {
        try command("endStatus", now: now)
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
    /// A replan (ADR-018) builds a new weekly program on acceptance, so it gets the program's id budget.
    public func acceptRecommendation(id: UUID, now: Date = Date()) throws {
        try command("acceptRecommendation", Arguments(id: id), now: now, idCount: Self.programIDCount)
    }
    public func rejectRecommendation(id: UUID, reason: String? = nil, now: Date = Date()) throws {
        try command("rejectRecommendation", Arguments(reason: reason, id: id), now: now)
    }

    // MARK: Read-only views computed by the core

    private struct StatePayload: Encodable {
        let state: AthleteState
        let permitsFixtures: Bool
        let now: Date
        let dayStart: Date
        let utcOffset: Int
    }
    /// Today's slot cards, pending proposal titles, the one slot (if any) to auto-request,
    /// recorded values per exercise and the Diet tab — one pass over the state after each change.
    /// `dayStart` is the start of the athlete's local day, so "today" follows their time zone, and
    /// `utcOffset` lets the core read the weekdays of logged sessions (ADR-018).
    public func views(now: Date = Date(), calendar: Calendar = .current) throws -> CoreViews {
        try core.call("views", StatePayload(state: repository.snapshot, permitsFixtures: library.permitsFixtures, now: now,
                                            dayStart: calendar.startOfDay(for: now),
                                            utcOffset: calendar.timeZone.secondsFromGMT(for: now)))
    }
    /// Available loads around a confirmed working load, in the athlete's own equipment step.
    public func loadSteps(base: Double, step: Double) throws -> [Double] {
        struct Steps: Encodable { let base: Double; let step: Double }
        return try core.call("loadSteps", Steps(base: base, step: step))
    }
    /// Checks the on-device model's `draft` of a set against the athlete's own `text`: a number
    /// survives only if the athlete said it. Read-only; the athlete saves the preview with `saveSet`.
    public func readSet(text: String, draft: SpokenSet) throws -> SetReading {
        struct Reading: Encodable {
            let state: AthleteState
            let text: String
            let draft: SpokenSet
            let permitsFixtures: Bool
        }
        return try core.call("readSet", Reading(state: repository.snapshot, text: text, draft: draft,
                                                permitsFixtures: library.permitsFixtures))
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

    // MARK: Diet (ADR-016)
    private struct DietProfileArguments: Encodable { let profile: DietProfile; let expected: DietTargets }
    private struct ExpectedArguments: Encodable { let expected: DietTargets }
    private struct WeighInArguments: Encodable { let weighIn: WeighIn }
    private struct WeighInsArguments: Encodable { let weighIns: [WeighIn] }
    private struct IDArguments: Encodable { let id: UUID }
    private struct FoodMealArguments: Encodable {
        let id: UUID; let foodID: Int; let grams: Double; let occurredAt: Date; let timeZone: String
    }

    /// The choices the diet setup screen offers, from the active diet policy.
    public func dietOptions(now: Date = Date()) throws -> DietOptions {
        struct Options: Encodable { let now: Date }
        return try core.call("dietOptions", Options(now: now))
    }
    /// What accepting `profile` would set, at the latest weigh-in. Nothing is stored.
    public func dietPreview(profile: DietProfile, now: Date = Date()) throws -> DietView {
        struct Preview: Encodable { let state: AthleteState; let profile: DietProfile; let now: Date }
        return try core.call("dietPreview", Preview(state: repository.snapshot, profile: profile, now: now))
    }
    /// Stores the profile and its targets; the core recomputes them and requires a match with `expected`.
    public func setDietTargets(profile: DietProfile, expected: DietTargets, now: Date = Date()) throws {
        try command("setDietTargets", DietProfileArguments(profile: profile, expected: expected), now: now)
    }
    /// Stores the athlete's answers without accepting targets; answers that withhold targets remove them.
    public func saveDietProfile(_ profile: DietProfile, now: Date = Date()) throws {
        struct ProfileArguments: Encodable { let profile: DietProfile }
        try command("saveDietProfile", ProfileArguments(profile: profile), now: now)
    }
    public func logWeighIn(_ weighIn: WeighIn, now: Date = Date()) throws {
        try command("logWeighIn", WeighInArguments(weighIn: weighIn), now: now)
    }
    /// Adds Apple Health weigh-ins the core has not stored yet; `true` when any were new.
    @discardableResult public func importWeighIns(_ weighIns: [WeighIn], now: Date = Date()) throws -> Bool {
        try command("importWeighIns", WeighInsArguments(weighIns: weighIns), now: now).value ?? false
    }
    public func deleteWeighIn(id: UUID) throws { try command("deleteWeighIn", IDArguments(id: id)) }
    public func acceptDietAdjustment(expected: DietTargets, now: Date = Date()) throws {
        try command("acceptDietAdjustment", ExpectedArguments(expected: expected), now: now)
    }
    public func rejectDietAdjustment(expected: DietTargets, now: Date = Date()) throws {
        try command("rejectDietAdjustment", ExpectedArguments(expected: expected), now: now)
    }
    /// Logs grams of a bundled USDA food; the core takes the nutrients from its own table.
    public func saveFoodMeal(foodID: Int, grams: Double, occurredAt: Date = Date(), id: UUID = UUID()) throws {
        try command("saveFoodMeal", FoodMealArguments(id: id, foodID: foodID, grams: grams, occurredAt: occurredAt,
                                                       timeZone: TimeZone.current.identifier), now: max(occurredAt, Date()))
    }
    /// Bundled USDA foods matching every word of `query`, optionally only those fitting `pattern`.
    public func searchFoods(_ query: String, pattern: DietPattern? = nil, limit: Int = 30) throws -> [FoodItem] {
        struct Search: Encodable { let query: String; let pattern: DietPattern?; let limit: Int }
        return try core.call("foods", Search(query: query, pattern: pattern, limit: limit))
    }
}
