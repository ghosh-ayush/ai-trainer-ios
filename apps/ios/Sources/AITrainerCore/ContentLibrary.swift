import Foundation

/// The exercises and progression policy the host offers to the Python core.
///
/// Swift only carries this data across the bridge; every judgement about it (eligibility,
/// substitution, progression) is made in `core/python`. No fixture value in this file is an
/// approved real-world training prescription — Release builds refuse `review: fixture` content.
public struct ContentLibrary {
    public let exercises: [Exercise]
    public let policy: TrainingPolicy
    public let permitsFixtures: Bool
    public init(permitsFixtures: Bool = false, exercises: [Exercise] = ContentLibrary.fixtureExercises,
                policy: TrainingPolicy = .developmentFixture) {
        self.permitsFixtures = permitsFixtures; self.exercises = exercises; self.policy = policy
    }
    public func exercise(_ id: String) -> Exercise? { exercises.first { $0.id == id } }
    /// Mirrors `content.is_enabled` in Python; used only for display decisions, never for guidance.
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
}
