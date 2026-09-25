import SwiftUI
import AITrainerCore

/// "What could change" on Today. The former Coach tab folded into this section (P1 simplification):
/// proposals now appear on the slot cards themselves, so only the boundary statement remains.
struct WhatCouldChangeSection: View {
    var body: some View {
        StitchSectionLabel("What could change")
        StitchNotice("Structured decisions, even in chat",
                     body: "Proposals need comparable recorded sets and your acceptance. Chat answers from your records and cited research and changes nothing by itself. Camera, sleep and meals never change your plan.")
    }
}

/// The chat head on Today: a round button that opens chat with the app (ADR-023).
struct ChatHeadButton: View {
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            Image(systemName: "bubble.left.and.text.bubble.right.fill")
                .font(.system(size: 22, weight: .semibold))
                .foregroundStyle(Stitch.accentOn)
                .frame(width: 58, height: 58)
                .background(Stitch.accentPrimary, in: Circle())
                .shadow(color: Stitch.accentSoft.opacity(0.45), radius: 12, y: 6)
        }
        .accessibilityLabel("Ask the app")
    }
}

/// One line of the conversation. Kept in memory while the app runs; nothing is saved (ADR-023).
struct ChatEntry: Identifiable {
    enum Content {
        case athlete(String)
        case reply(ChatReply)
        case note(String)
    }
    let id = UUID()
    let content: Content
}

/// A sheet chat opens on top of itself: the same sheets Today uses, so every change goes through
/// its usual preview and Accept.
enum ChatRoute: Identifiable {
    case load(Prescription)
    case swap(Prescription)
    case lessTime(Int?)
    case moveDay
    case pain
    case status
    case changeDays

    var id: String {
        switch self {
        case .load(let slot): return "load-\(slot.id)"
        case .swap(let slot): return "swap-\(slot.id)"
        case .lessTime(let minutes): return "lessTime-\(minutes ?? 0)"
        case .moveDay: return "moveDay"
        case .pain: return "pain"
        case .status: return "status"
        case .changeDays: return "changeDays"
        }
    }
}

/// Chat with the app (ADR-023). Apple's on-device model only reads a typed message into a topic and
/// the details said; the Python core writes every answer from the athlete's records and the cited
/// content. Questions can also be tapped, which skips the model, so chat works where it cannot run.
/// Nothing changes until the athlete taps an action, and plan changes are still proposals.
struct CoachChatSheet: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    @Binding var entries: [ChatEntry]
    @State private var text = ""
    @State private var isReading = false
    @State private var starters: [ChatAction] = []
    @State private var route: ChatRoute?
    @State private var confirmSkip = false

    var body: some View {
        VStack(spacing: 0) {
            StitchSheetHeader("Ask the app") { dismiss() }
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 12) {
                        introduction
                        ForEach(entries) { entry in
                            entryView(entry).id(entry.id)
                        }
                        if isReading {
                            HStack(spacing: 8) {
                                ProgressView().tint(Stitch.accentPrimary)
                                Text("Reading…").stitch(.body13).foregroundStyle(Stitch.textMuted)
                            }
                            .id("reading")
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 12)
                    .padding(.bottom, 16)
                }
                .scrollDismissesKeyboard(.interactively)
                .onChange(of: entries.count) {
                    guard let last = entries.last else { return }
                    withAnimation { proxy.scrollTo(last.id, anchor: .top) }
                }
            }
            inputBar
        }
        .background { StitchBackdrop().opacity(0.9) }
        .presentationDragIndicator(.visible)
        .presentationBackground(Stitch.glassSheet)
        .presentationCornerRadius(28)
        .preferredColorScheme(.dark)
        .sheet(item: $route) { route in
            routeView(route)
        }
        .confirmationDialog("Skip this session? Work will not be added to the next session.", isPresented: $confirmSkip,
                            titleVisibility: .visible) {
            Button("Skip session", role: .destructive) {
                store.perform({ try $0.skip() }) { _ in note("Skipped. The next session is up on Today.") }
            }
        }
        .task { loadStarters() }
    }

    // MARK: Parts

    @ViewBuilder private var introduction: some View {
        StitchNotice("Answers from your own records",
                     body: "Ask about your training, your week, less time, pain or where the numbers come from. Answers come from your logged sets and the app's cited research. Nothing changes until you tap a button, and plan changes still need Accept.")
        if !starters.isEmpty {
            StitchSectionLabel("Try asking")
            ForEach(Array(starters.enumerated()), id: \.offset) { _, action in
                Button(action.title) { perform(action) }.buttonStyle(.stitch(.secondary, compact: true))
            }
        }
    }

    @ViewBuilder private func entryView(_ entry: ChatEntry) -> some View {
        switch entry.content {
        case .athlete(let message):
            HStack {
                Spacer(minLength: 48)
                Text(message).stitch(.body15).foregroundStyle(Stitch.textPrimary)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .glass(radius: 16, fill: Stitch.glassSurface2)
            }
        case .reply(let reply):
            ChatReplyView(reply: reply, onAction: perform)
        case .note(let message):
            StitchFootnote(message)
        }
    }

    @ViewBuilder private var inputBar: some View {
        if OnDeviceChatReader.isAvailable {
            HStack(spacing: 8) {
                TextField("Ask about your training", text: $text)
                    .stitch(.body15)
                    .foregroundStyle(Stitch.textPrimary)
                    .submitLabel(.send)
                    .onSubmit(send)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .glass(radius: 20, fill: Stitch.glassSurface)
                Button(action: send) {
                    Image(systemName: "arrow.up.circle.fill").font(.system(size: 32))
                }
                .foregroundStyle(canSend ? Stitch.accentPrimary : Stitch.textDisabled)
                .disabled(!canSend)
                .accessibilityLabel("Send")
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background(Stitch.glassChrome)
            .overlay(alignment: .top) { Stitch.strokeHairline.frame(height: 1) }
        } else {
            StitchFootnote("Typing a question needs Apple Intelligence on this iPhone. Tap a question instead.")
                .padding(16)
        }
    }

    @ViewBuilder private func routeView(_ route: ChatRoute) -> some View {
        switch route {
        case .load(let slot): LoadSheet(slot: slot)
        case .swap(let slot): SwapSheet(slot: slot)
        case .lessTime(let minutes): LessTimeSheet(minutes: minutes)
        case .moveDay: MoveDaySheet()
        case .pain: PainSheet()
        case .status: StatusSheet()
        case .changeDays:
            if let profile = store.state.profile { ChangeDaysSheet(profile: profile) }
        }
    }

    // MARK: Asking

    private var canSend: Bool {
        !isReading && !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    /// The core's own starter questions, so the buttons here match the ones it offers when unsure.
    private func loadStarters() {
        guard starters.isEmpty else { return }
        store.read({ try $0.chat(text: "Help", draft: ChatDraft(topic: .other)) }, then: { reply in
            starters = reply.actions
        }, failed: { _ in })
    }

    /// A typed message: the on-device model reads it, then the core answers.
    private func send() {
        let message = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !message.isEmpty, !isReading else { return }
        text = ""
        entries.append(ChatEntry(content: .athlete(message)))
        isReading = true
        let names = store.service?.chatExerciseNames ?? []
        Task { @MainActor in
            do {
                let draft = try await OnDeviceChatReader.draft(from: message, exerciseNames: names)
                answer(message, draft: draft)
            } catch {
                // The core still reads pain words and offers its questions, so an answer comes anyway.
                note(Self.unreadable(error))
                answer(message, draft: ChatDraft(topic: .other))
            }
        }
    }

    /// Sends `message` with `draft` to the core and shows its answer.
    private func answer(_ message: String, draft: ChatDraft) {
        isReading = true
        store.read({ try $0.chat(text: message, draft: draft) }, then: { reply in
            isReading = false
            entries.append(ChatEntry(content: .reply(reply)))
        }, failed: { error in
            isReading = false
            note(error.localizedDescription)
        })
    }

    /// Why the model's reading is missing. The model's own error only helps while developing.
    private static func unreadable(_ error: Error) -> String {
        #if DEBUG
        return "Apple's on-device model couldn't read that here (\(error.localizedDescription))."
        #else
        return "Apple's on-device model couldn't read that right now."
        #endif
    }

    private func note(_ message: String) {
        entries.append(ChatEntry(content: .note(message)))
    }

    // MARK: Actions

    /// Runs one tapped action. Plan changes go through the usual request, which only proposes.
    private func perform(_ action: ChatAction) {
        switch action.kind {
        case .ask:
            guard let message = action.message, let draft = action.draft, !isReading else { return }
            entries.append(ChatEntry(content: .athlete(message)))
            answer(message, draft: draft)
        case .openToday:
            leave(to: .today)
        case .openDiet:
            leave(to: .diet)
        case .openLoad:
            if let slot = slot(action.slotID) { route = .load(slot) }
        case .openSwap:
            if let slot = slot(action.slotID) { route = .swap(slot) }
        case .openLessTime:
            route = .lessTime(action.minutes)
        case .openMoveDay:
            route = .moveDay
        case .openPain:
            route = .pain
        case .openStatus:
            route = .status
        case .openChangeDays:
            route = .changeDays
        case .confirmSkip:
            confirmSkip = true
        case .requestProgression:
            guard let slotID = action.slotID else { return }
            store.request(.progression(slotID))
            leave(to: .today)
        case .requestShorten:
            guard let minutes = action.minutes else { return }
            store.request(.shorten(minutes))
            leave(to: .today)
        case .requestReplan:
            store.request(.replan(utcOffset: TimeZone.current.secondsFromGMT()))
            leave(to: .today)
        case .reportPain:
            guard let exerciseID = action.exerciseID else { return }
            store.perform({ try $0.reportPain(exerciseID: exerciseID) }) { _ in
                note("Guidance for \(store.name(exerciseID)) is paused. Swap it on Today when you're ready.")
            }
        case .setStatus:
            guard let status = action.status else { return }
            store.perform({ try $0.setStatus(status, endsAt: action.endsAt) }) { _ in
                let until = action.endsAt.map { " until \($0.formatted(date: .abbreviated, time: .omitted))" } ?? " until you tap I'm back"
                note("Marked \(status.label.lowercased())\(until). The app's own suggestions are paused; your plan is unchanged.")
            }
        case .endStatus:
            store.perform({ try $0.endStatus() }) { _ in
                note("Welcome back. The app's suggestions are on again.")
            }
        }
    }

    private func slot(_ id: UUID?) -> Prescription? {
        guard let id else { return nil }
        return (store.state.activeSession?.plan ?? store.state.nextPlan)?.slots.first { $0.id == id }
    }

    /// Closes chat on a tab, where a requested proposal appears for Accept.
    private func leave(to tab: AppTab) {
        store.tab = tab
        dismiss()
    }
}

/// One answer: how the message was read, the lines the core wrote, what was left out, the
/// actions to tap and the sources behind it.
struct ChatReplyView: View {
    let reply: ChatReply
    let onAction: (ChatAction) -> Void
    @State private var showSources = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Read as · \(reply.reading)").stitch(.monoLabel).textCase(.uppercase).foregroundStyle(Stitch.textMuted)
            ForEach(Array(reply.lines.enumerated()), id: \.offset) { _, line in
                Text(line).stitch(.body15).foregroundStyle(Stitch.textPrimary).fixedSize(horizontal: false, vertical: true)
            }
            if !reply.ignored.isEmpty {
                StitchFootnote("Left out because you didn't say it: \(ignoredText).")
            }
            ForEach(Array(reply.actions.enumerated()), id: \.offset) { _, action in
                Button(action.title) { onAction(action) }
                    .buttonStyle(.stitch(action.kind == .reportPain ? .destructive : .secondary, compact: true))
            }
            if !reply.sources.isEmpty {
                Button(showSources ? "Hide sources" : "Sources (\(reply.sources.count))") { showSources.toggle() }
                    .buttonStyle(.stitch(.link))
                if showSources {
                    ForEach(reply.sources, id: \.key) { source in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(source.citation).stitch(.body13).foregroundStyle(Stitch.textSecondary)
                            if let identifier = sourceIdentifier(source) {
                                StitchFootnote(identifier)
                            }
                        }
                        .textSelection(.enabled)
                    }
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .glass(radius: 14)
    }

    private var ignoredText: String {
        let names = ["exercise": "an exercise", "minutes": "a number of minutes", "days": "a number of days"]
        return reply.ignored.map { names[$0] ?? $0 }.joined(separator: ", ")
    }

    private func sourceIdentifier(_ source: ChatSource) -> String? {
        let parts = [source.doi.map { "DOI \($0)" }, source.pmid.map { "PMID \($0)" }].compactMap { $0 }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }
}
