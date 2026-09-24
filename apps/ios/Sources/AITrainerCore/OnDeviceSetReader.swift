import Foundation
#if canImport(FoundationModels)
import FoundationModels
#endif

/// Reads a set the athlete described in words with Apple's on-device language model (ADR-015).
///
/// The model runs on the phone (no network) and only drafts a `SpokenSet`: which exercise, and
/// which of the athlete's numbers are reps, load and reps in reserve. It decides nothing.
/// `TrainerService.readSet` sends the draft and the athlete's words to Python, which keeps a
/// number only if the athlete said it; the athlete then saves the preview with an explicit tap.
///
/// Where the model is unavailable (before iOS 26, an ineligible device, Apple Intelligence off
/// or still downloading) `isAvailable` is false and the app offers no words entry at all.
public enum OnDeviceSetReader {
    /// Whether the on-device model can run right now.
    public static var isAvailable: Bool {
        #if canImport(FoundationModels)
        if #available(iOS 26.0, macOS 26.0, *) {
            return SystemLanguageModel.default.isAvailable
        }
        #endif
        return false
    }

    /// The model's draft of one set from the athlete's `text`. `exerciseNames` are the session's
    /// exercises; the model may only name one of them, or none.
    public static func draft(from text: String, exerciseNames: [String]) async throws -> SpokenSet {
        #if canImport(FoundationModels)
        if #available(iOS 26.0, macOS 26.0, *) {
            return try await OnDeviceSetModel.draft(from: text, exerciseNames: exerciseNames)
        }
        #endif
        throw TrainerError.unsupported
    }
}

#if canImport(FoundationModels)
@available(iOS 26.0, macOS 26.0, *)
private enum OnDeviceSetModel {
    static let instructions = """
        You read one gym set that an athlete describes and fill in its fields.
        Copy each number exactly as the athlete said it. Leave a field empty when the athlete \
        did not say it. Never estimate, round, convert or complete a value.
        reps: repetitions completed in this set.
        load: the weight lifted, as said, without its unit.
        rir: reps in reserve, how many more reps the athlete said they could have done.
        exercise: the exercise the athlete named, from the allowed list. Leave it empty when \
        the athlete named none.
        """

    static func draft(from text: String, exerciseNames: [String]) async throws -> SpokenSet {
        let schema = try GenerationSchema(root: root(exerciseNames: exerciseNames), dependencies: [])
        let session = LanguageModelSession(instructions: instructions)
        let response = try await session.respond(to: text, schema: schema,
                                                 options: GenerationOptions(samplingMode: .greedy))
        let content = response.content
        let exercise = exerciseNames.isEmpty ? nil : try content.value(String?.self, forProperty: "exercise")
        return SpokenSet(exercise: exercise,
                         reps: try content.value(Int?.self, forProperty: "reps"),
                         load: try content.value(Double?.self, forProperty: "load"),
                         rir: try content.value(Int?.self, forProperty: "rir"))
    }

    /// Every field is optional so the model can leave out what the athlete did not say. Measured on
    /// 2026-09-23: without explicit nulls the model filled unsaid fields with 0 ("did 10 reps" came
    /// back with load 0 and RIR 0); with them it returned null. Python drops such values either way.
    private static func root(exerciseNames: [String]) -> DynamicGenerationSchema {
        var properties: [DynamicGenerationSchema.Property] = []
        var names: [String] = []
        for name in exerciseNames where !names.contains(name) {
            names.append(name)
        }
        if !names.isEmpty {
            properties.append(.init(name: "exercise", description: "The exercise the athlete named",
                                    schema: DynamicGenerationSchema(name: "Exercise", anyOf: names), isOptional: true))
        }
        properties.append(.init(name: "reps", description: "Repetitions completed",
                                schema: DynamicGenerationSchema(type: Int.self, guides: [.range(0...1000)]), isOptional: true))
        properties.append(.init(name: "load", description: "Weight lifted, without its unit",
                                schema: DynamicGenerationSchema(type: Double.self, guides: [.minimum(0)]), isOptional: true))
        properties.append(.init(name: "rir", description: "Reps in reserve the athlete said",
                                schema: DynamicGenerationSchema(type: Int.self, guides: [.range(0...10)]), isOptional: true))
        if #available(iOS 26.4, macOS 26.4, *) {
            return DynamicGenerationSchema(name: "SpokenSet", representNilExplicitlyInGeneratedContent: true,
                                           properties: properties)
        }
        return DynamicGenerationSchema(name: "SpokenSet", properties: properties)
    }
}
#endif
