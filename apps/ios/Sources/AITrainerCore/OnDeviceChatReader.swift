import Foundation
#if canImport(FoundationModels)
import FoundationModels
#endif

/// Reads a chat message with Apple's on-device language model (ADR-023).
///
/// The model runs on the phone (no network) and only sorts the message into a `ChatDraft`: one
/// topic from a fixed list, and any exercise, minutes or days it saw. It never answers.
/// `TrainerService.chat` sends the draft and the athlete's words to Python, which keeps an
/// exercise or a number only if the athlete said it and writes the whole answer from the
/// athlete's records and the cited content.
///
/// Where the model is unavailable (before iOS 26, an ineligible device, Apple Intelligence off
/// or still downloading) `isAvailable` is false; chat then offers its questions as buttons only.
public enum OnDeviceChatReader {
    /// Whether the on-device model can run right now.
    public static var isAvailable: Bool {
        #if canImport(FoundationModels)
        if #available(iOS 26.0, macOS 26.0, *) {
            return SystemLanguageModel.default.isAvailable
        }
        #endif
        return false
    }

    /// The model's reading of the athlete's `text`. `exerciseNames` are the plan's exercises; the
    /// model may only name one of them, or none.
    public static func draft(from text: String, exerciseNames: [String]) async throws -> ChatDraft {
        #if canImport(FoundationModels)
        if #available(iOS 26.0, macOS 26.0, *) {
            return try await OnDeviceChatModel.draft(from: text, exerciseNames: exerciseNames)
        }
        #endif
        throw TrainerError.unsupported
    }
}

#if canImport(FoundationModels)
@available(iOS 26.0, macOS 26.0, *)
private enum OnDeviceChatModel {
    /// Measured on 2026-09-25 with 40 sample messages on the Mac's on-device model: 37 topics right.
    /// The misses (pain read as a break, "how am I doing overall" as one exercise) are covered by
    /// the core, which always answers pain words as pain and gives an overview when no exercise is named.
    static let instructions = """
        You sort one message an athlete sends to their training app into a topic and copy out the \
        details they gave. You never answer the message.
        topic, choose one:
        exerciseProgress: how the athlete is doing on one exercise, why its weight or reps are not going up, \
        or what to lift on it next time.
        nextSession: what today's or the next workout is.
        week: the weekly plan, which days, how many sessions, how much each muscle gets this week.
        lessTime: the athlete has less time than planned for a workout.
        moveOrSkip: the athlete cannot train on the planned day and wants to move or skip it.
        pain: something hurts, pain, an injury or a sore body part.
        away: the athlete is sick, ill, on holiday, travelling, taking a break, or back from one.
        changePlan: the athlete wants the plan lighter, harder, different exercises or different days.
        evidence: why the plan uses a number such as its reps, sets, rest or weight steps, where the numbers \
        come from, or the research behind them.
        diet: food, calories, protein, meals or body weight.
        other: anything else.
        exercise: the exercise the athlete named, from the allowed list. Leave it empty when none was named.
        minutes: minutes the athlete said they have. Leave it empty when not said.
        days: a number of days the athlete said. Leave it empty when not said.
        Copy numbers exactly as said. Never guess a value the athlete did not say.
        """

    static func draft(from text: String, exerciseNames: [String]) async throws -> ChatDraft {
        let schema = try GenerationSchema(root: root(exerciseNames: exerciseNames), dependencies: [])
        let session = LanguageModelSession(instructions: instructions)
        let response = try await session.respond(to: text, schema: schema,
                                                 options: GenerationOptions(samplingMode: .greedy))
        let content = response.content
        let topicName = try content.value(String.self, forProperty: "topic")
        let exercise = exerciseNames.isEmpty ? nil : try content.value(String?.self, forProperty: "exercise")
        return ChatDraft(topic: ChatTopic(rawValue: topicName) ?? .other,
                         exercise: exercise,
                         minutes: try content.value(Int?.self, forProperty: "minutes"),
                         days: try content.value(Int?.self, forProperty: "days"))
    }

    /// The topic is required and limited to the core's topics. Every other field is optional with
    /// explicit nulls, so the model can leave out what the athlete did not say; it still fills
    /// some anyway (measured: "why is my squat not going up" came back with 15 minutes and 3 days),
    /// which is why Python keeps only what the athlete's own words contain.
    private static func root(exerciseNames: [String]) -> DynamicGenerationSchema {
        var properties: [DynamicGenerationSchema.Property] = [
            .init(name: "topic", description: "What the message is about",
                  schema: DynamicGenerationSchema(name: "Topic", anyOf: ChatTopic.allCases.map(\.rawValue))),
        ]
        var names: [String] = []
        for name in exerciseNames where !names.contains(name) {
            names.append(name)
        }
        if !names.isEmpty {
            properties.append(.init(name: "exercise", description: "The exercise the athlete named",
                                    schema: DynamicGenerationSchema(name: "Exercise", anyOf: names), isOptional: true))
        }
        properties.append(.init(name: "minutes", description: "Minutes the athlete said they have",
                                schema: DynamicGenerationSchema(type: Int.self, guides: [.range(1...600)]), isOptional: true))
        properties.append(.init(name: "days", description: "Number of days the athlete said",
                                schema: DynamicGenerationSchema(type: Int.self, guides: [.range(1...365)]), isOptional: true))
        if #available(iOS 26.4, macOS 26.4, *) {
            return DynamicGenerationSchema(name: "ChatReading", representNilExplicitlyInGeneratedContent: true,
                                           properties: properties)
        }
        return DynamicGenerationSchema(name: "ChatReading", properties: properties)
    }
}
#endif
