import SwiftUI
import AITrainerCore

/// "What could change" on Today. The former Coach tab folded into this section (P1 simplification):
/// proposals now appear on the slot cards themselves, so only the boundary statement remains.
struct WhatCouldChangeSection: View {
    var body: some View {
        StitchSectionLabel("What could change")
        StitchNotice("Structured decisions, not a chatbot",
                     body: "Proposals need comparable recorded sets and your acceptance. Camera, sleep and meals never change your plan.")
    }
}
