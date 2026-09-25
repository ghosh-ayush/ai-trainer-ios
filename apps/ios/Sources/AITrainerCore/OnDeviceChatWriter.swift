import Foundation
#if canImport(FoundationModels)
import FoundationModels
#endif

/// Rewrites the app's chat answer as a conversational reply with Apple's on-device model (ADR-027).
///
/// The core has already written the answer as plain facts (`ChatReply.lines`), from the athlete's
/// records and the cited content. The model only rephrases them, deterministically, under strict
/// rules: say only what the facts say, never contradict them, add nothing. The result is not
/// shown until `TrainerService.checkChatWording` confirms every number and exercise in it is
/// grounded; otherwise the facts are shown as written. Pain answers are never sent here.
public enum OnDeviceChatWriter {
    /// The model's reply to `message` from `reply`'s facts. Throws where the model can't run.
    public static func reply(to message: String, facts reply: ChatReply, earlier: String? = nil) async throws -> String {
        #if canImport(FoundationModels)
        if #available(iOS 26.0, macOS 26.0, *) {
            return try await OnDeviceChatVoice.reply(to: message, facts: reply, earlier: earlier)
        }
        #endif
        throw TrainerError.unsupported
    }
}

#if canImport(FoundationModels)
@available(iOS 26.0, macOS 26.0, *)
private enum OnDeviceChatVoice {
    /// Measured on 2026-09-25 with 7 real answers on the Mac's model: with these rules and greedy
    /// sampling every number stayed grounded and no fact was contradicted; freer wording (temperature,
    /// looser rules) invented claims and once said the opposite of the facts.
    static let instructions = """
        You turn a training app's answer into a short, friendly chat reply to the athlete.
        The FACTS are numbered. Say what they say, in plain words, in 2 or 3 sentences. Start with the fact \
        that answers the athlete's question.
        Rules:
        - Every sentence must say only what one of the FACTS says. Never contradict a fact: if a fact says a \
        change is ready, don't say nothing is changing.
        - Never add anything the FACTS don't say: no number, exercise, rule, study, time, weight, advice or reason.
        - Keep every number you use exactly as written.
        - No lists. Don't mention buttons. Don't greet, sign off or claim to be a person.
        """

    static func reply(to message: String, facts reply: ChatReply, earlier: String?) async throws -> String {
        let facts = reply.lines.enumerated().map { "\($0.offset + 1). \($0.element)" }.joined(separator: "\n")
        var prompt = ""
        if let earlier {
            prompt += "Earlier the athlete asked: \"\(earlier)\"\n"
        }
        prompt += """
            The athlete wrote: "\(message)"
            FACTS (the app's answer, read as: \(reply.reading)):
            \(facts)
            Write your reply.
            """
        let session = LanguageModelSession(instructions: instructions)
        let response = try await session.respond(to: prompt,
                                                 options: GenerationOptions(samplingMode: .greedy, maximumResponseTokens: 200))
        return response.content
    }
}
#endif
