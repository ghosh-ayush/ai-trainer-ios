import AVFoundation
import Foundation

/// ADR-022: reads the core's workout cues aloud with the system voice. It speaks only text the
/// core built from the plan and logged sets (`workoutCues`); it adds nothing of its own.
/// Music ducks while it speaks and comes back after. It speaks while the app is on screen.
@MainActor
public final class SpokenCoach: NSObject, AVSpeechSynthesizerDelegate {
    private let synthesizer = AVSpeechSynthesizer()

    public override init() {
        super.init()
        synthesizer.delegate = self
    }

    /// Say `text`, interrupting anything this coach was still saying.
    public func say(_ text: String) {
        #if os(iOS)
        let audio = AVAudioSession.sharedInstance()
        try? audio.setCategory(.playback, mode: .spokenAudio, options: [.duckOthers, .interruptSpokenAudioAndMixWithOthers])
        try? audio.setActive(true)
        #endif
        synthesizer.stopSpeaking(at: .word)
        synthesizer.speak(AVSpeechUtterance(string: text))
    }

    nonisolated public func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        #if os(iOS)
        // Let other audio return to full volume once the cue is spoken.
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        #endif
    }
}
