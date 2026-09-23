import Foundation

/// Descriptive reference records imported from free-exercise-db (public domain).
/// Browsing them never enrols an exercise into guidance. The bundled file's shape and unique
/// ids are checked by `core/python/tests/test_contract.py`, not at runtime.
public struct ExerciseCatalog {
    public static let sourceRevision = "a859101d633a01c4a1a920d6a8ce41dabba0705f"
    public let exercises: [CatalogExercise]
    public static func bundled() throws -> ExerciseCatalog {
        guard let url = Bundle.module.url(forResource: "exercises", withExtension: "json") else { throw TrainerError.notFound }
        return ExerciseCatalog(exercises: try JSONDecoder().decode([CatalogExercise].self, from: Data(contentsOf: url)))
    }
}
