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
        try LocalPythonTrainerService.shared.initialProgram(profile: profile, library: self, now: now)
    }
    public func context(for exercise: Exercise, unit: MassUnit) -> EquipmentContext {
        .init(id: "local-\(exercise.id)", name: "My \(exercise.name) equipment", kind: exercise.equipmentKind,
              unit: unit, basis: exercise.basis)
    }
}

public struct TrainingBrain {
    public let library: ContentLibrary
    public init(library: ContentLibrary) {
        self.library = library
    }
    public func decide(state: AthleteState, request: Request, now: Date) -> Decision {
        do { return try LocalPythonTrainerService.shared.decide(state: state, request: request, library: library, now: now) }
        catch { return .init(.withholdGuidance, "LOCAL_CORE_UNAVAILABLE", "Local training rules could not run. No change was applied.") }
    }
}
