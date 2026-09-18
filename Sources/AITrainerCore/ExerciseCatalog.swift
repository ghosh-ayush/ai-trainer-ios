import Foundation

/// Descriptive upstream data only. This type deliberately has no review, load basis,
/// alternatives, progression, or camera-support policy fields and cannot become Exercise.
public struct CatalogExercise: Decodable, Equatable, Identifiable {
    public let id: String
    public let name: String
    public let force: String?
    public let level: String
    public let mechanic: String?
    public let equipment: String?
    public let primaryMuscles: [String]
    public let secondaryMuscles: [String]
    public let instructions: [String]
    public let category: String
    public let images: [String]
}

public struct ExerciseCatalog {
    public static let sourceRevision = "a859101d633a01c4a1a920d6a8ce41dabba0705f"
    public let exercises: [CatalogExercise]
    public init(data: Data) throws {
        let decoded = try JSONDecoder().decode([CatalogExercise].self, from: data)
        guard Set(decoded.map(\.id)).count == decoded.count else {
            throw TrainerError.invalid("Duplicate exercise catalog identifiers.")
        }
        exercises = decoded
    }
    public static func bundled() throws -> ExerciseCatalog {
        guard let url = Bundle.module.url(forResource: "exercises", withExtension: "json") else { throw TrainerError.notFound }
        return try ExerciseCatalog(data: Data(contentsOf: url))
    }
    public func exercise(_ id: String) -> CatalogExercise? { exercises.first { $0.id == id } }
    /// Explicit descriptive links only; unmapped governed exercises stay unmapped.
    public func description(for exercise: Exercise) -> CatalogExercise? {
        guard let id = Self.governedLinks[exercise.id] else { return nil }
        return self.exercise(id)
    }
    public static let governedLinks = ["bench": "Barbell_Bench_Press_-_Medium_Grip", "goblet_squat": "Goblet_Squat"]
}
