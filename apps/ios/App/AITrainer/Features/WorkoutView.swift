import SwiftUI
import AITrainerCore

private struct SetEntry: Identifiable {
    let id = UUID()
    let sessionID: UUID
    let slot: Prescription
    let index: Int
}

/// P07 Workout: one tap logs a set as planned; anything else goes through the set sheet.
/// Unknown load stays unknown and a one-tap set records no reps-in-reserve.
struct WorkoutView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    @State private var entry: SetEntry?
    @State private var showFinish = false
    @State private var showPain = false
    @State private var showWords = false
    var body: some View {
        Group {
            if let session = store.state.activeSession {
                ScrollViewReader { proxy in
                    DetailScreen("Workout") { sessionContent(session) }
                        // After each save, bring the next set still to log into view.
                        .onChange(of: session.logs.count) {
                            guard let next = Self.nextUnloggedSet(in: session) else { return }
                            withAnimation { proxy.scrollTo(Self.rowID(slot: next.slot.id, index: next.index), anchor: .center) }
                        }
                }
            } else {
                DetailScreen("Workout") {
                    StitchCard("Session saved", body: "Review what you recorded in Progress. Next-session proposals appear on Today.", tone: .accent)
                    Button("Back to Today") { dismiss() }.buttonStyle(.stitch())
                }
            }
        }
        .sheet(item: $entry) { SetSheet(sessionID: $0.sessionID, slot: $0.slot, workingIndex: $0.index) }
        .sheet(isPresented: $showPain) { PainSheet() }
        .sheet(isPresented: $showWords) { SpokenSetSheet() }
        .sheet(isPresented: $showFinish) {
            FinishSheet { finishedID in
                store.justFinishedSessionID = finishedID
                showFinish = false
                dismiss()
            }
        }
    }

    @ViewBuilder private func sessionContent(_ session: WorkoutSession) -> some View {
        let paused = session.status == .paused
        timer(session)
        StitchSectionLabel("Status: \(paused ? "paused" : "in progress")",
                           meta: "\(session.completeWorkingSets) working set\(session.completeWorkingSets == 1 ? "" : "s") recorded")
        // Offered only where Apple's on-device model runs; every other path works without it (ADR-015).
        if OnDeviceSetReader.isAvailable {
            Button("Log a set in words") { showWords = true }.buttonStyle(.stitch(.secondary)).disabled(paused)
        }
        ForEach(session.plan.slots) { slot in
            StitchSectionLabel(store.name(slot.exerciseID), meta: "Target \(slot.load.map(number) ?? "unknown") \(slot.equipment.unit.rawValue) · \(slot.equipment.basis.label)")
            if let last = store.progress.first(where: { $0.exerciseID == slot.exerciseID })?.entries.first {
                Text("Last time: \(last.summary)").stitch(.body13).foregroundStyle(Stitch.textSecondary)
            }
            PlateLine(slot: slot)
            ForEach(0..<slot.workingSets, id: \.self) { index in
                Group {
                    if let log = Self.workingLog(in: session, slot: slot.id, index: index) {
                        StitchLoggedSet(index: index + 1, result: "\(log.reps) reps @ \(log.load.map { "\(number($0)) \(log.unit.rawValue)" } ?? "unknown load")",
                                        rir: log.rir.map { "RIR \($0)" } ?? "RIR —")
                    } else {
                        Button(doneLabel(slot: slot, index: index)) { logAsPlanned(session: session, slot: slot, index: index) }
                            .buttonStyle(.stitch())
                            .disabled(paused)
                        if let previous = Self.sameAsLast(in: session, slot: slot, index: index) {
                            Button("Same as last · \(previous.reps) reps · \(previous.load.map { "\(number($0)) \(previous.unit.rawValue)" } ?? "load unknown")") {
                                logSameAsLast(session: session, slot: slot, index: index, previous: previous)
                            }
                            .buttonStyle(.stitch(.secondary))
                            .disabled(paused)
                        }
                    }
                }
                .id(Self.rowID(slot: slot.id, index: index))
            }
            Button("Adjust · warm-up · extra set") {
                entry = SetEntry(sessionID: session.id, slot: slot, index: Self.firstOpenIndex(in: session, slot: slot) ?? 0)
            }
            .buttonStyle(.stitch(.link)).disabled(paused)
        }
        Button("I'm in pain — pause guidance") { showPain = true }.buttonStyle(.stitch(.destructive))
        Button(paused ? "Resume session" : "Pause session") { store.perform { try $0.setPaused(!paused) } }
            .buttonStyle(.stitch(.secondary))
        Button("Finish") { showFinish = true }.buttonStyle(.stitch())
    }

    /// S/Timer: paused, resting (deadline-based, survives relaunch) or rest complete.
    @ViewBuilder private func timer(_ session: WorkoutSession) -> some View {
        let next = Self.nextUnloggedSet(in: session).map { "Next: set \($0.index + 1) · \($0.slot.targets[$0.index]) reps · \(loadText($0.slot))" } ?? "All planned sets recorded"
        if session.status == .paused {
            StitchTimer("Paused", value: "—", caption: "Resume to keep logging")
        } else if let activity = WorkoutActivity(session: session), activity.restEndsAt != nil {
            TimelineView(.periodic(from: .now, by: 1)) { context in
                let remaining = activity.remainingRestSeconds(at: context.date)
                StitchTimer(remaining == 0 ? "Rest complete" : "Rest",
                            value: String(format: "%02d:%02d", remaining / 60, remaining % 60), caption: next)
            }
        }
    }

    private func doneLabel(slot: Prescription, index: Int) -> String {
        "Done as planned · \(slot.targets[index]) reps · \(loadText(slot))"
    }
    private func loadText(_ slot: Prescription) -> String {
        slot.load.map { "\(number($0)) \(slot.equipment.unit.rawValue)" } ?? "load unknown"
    }
    /// ADR-021: repeat the previous set's reps and load. Effort is never copied, so RIR stays unknown.
    private func logSameAsLast(session: WorkoutSession, slot: Prescription, index: Int, previous: SetLog) {
        store.perform { try $0.saveSet(sessionID: session.id, slotID: slot.id, index: index, load: previous.load, reps: previous.reps, rir: nil) }
    }
    /// The next open working set can repeat the set just before it, when that one differs from the plan.
    static func sameAsLast(in session: WorkoutSession, slot: Prescription, index: Int) -> SetLog? {
        guard index > 0, firstOpenIndex(in: session, slot: slot) == index,
              let previous = workingLog(in: session, slot: slot.id, index: index - 1) else { return nil }
        let planned = slot.targets.indices.contains(index) ? slot.targets[index] : slot.lowerReps
        return previous.reps == planned && previous.load == slot.load ? nil : previous
    }
    /// One tap: the planned reps at the planned load. Effort is not assumed, so RIR stays unknown.
    private func logAsPlanned(session: WorkoutSession, slot: Prescription, index: Int) {
        store.perform { try $0.saveSet(sessionID: session.id, slotID: slot.id, index: index, load: slot.load, reps: slot.targets[index], rir: nil) }
    }

    static func rowID(slot: UUID, index: Int) -> String { "\(slot.uuidString)-\(index)" }
    static func workingLog(in session: WorkoutSession, slot: UUID, index: Int) -> SetLog? {
        session.logs.first { $0.prescriptionID == slot && $0.index == index && $0.kind == .working }
    }
    static func firstOpenIndex(in session: WorkoutSession, slot: Prescription) -> Int? {
        (0..<slot.workingSets).first { workingLog(in: session, slot: slot.id, index: $0) == nil }
    }
    /// The first planned working set, in plan order, that has no log yet.
    static func nextUnloggedSet(in session: WorkoutSession) -> (slot: Prescription, index: Int)? {
        for slot in session.plan.slots {
            if let index = firstOpenIndex(in: session, slot: slot) { return (slot, index) }
        }
        return nil
    }
}

/// P08: log a set that differs from the plan, or a warm-up / extra set. Unknown stays unknown.
struct SetSheet: View {
    enum Kind: String, CaseIterable { case working = "Working", warmUp = "Warm-up", extra = "Extra" }
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    let sessionID: UUID
    let slot: Prescription
    let workingIndex: Int
    @State private var kind: Kind = .working
    @State private var load: Double?
    @State private var reps = 0
    @State private var rir: Int?
    @State private var logID = UUID()
    @State private var operationID = UUID()
    var body: some View {
        Group {
            StitchSectionLabel(store.name(slot.exerciseID),
                               meta: "\(kind == .working ? "Set \(workingIndex + 1) of \(slot.workingSets)" : kind.rawValue) · \(slot.equipment.basis.label) · \(slot.equipment.unit.rawValue)")
            StitchSectionLabel("Kind")
            HStack(spacing: 10) {
                ForEach(Kind.allCases, id: \.self) { option in
                    Button(option.rawValue) { kind = option }.buttonStyle(.stitch(kind == option ? .primary : .secondary))
                }
            }
            StitchField("Load · \(slot.equipment.unit.rawValue) (clear = unknown)", value: load.map(number) ?? "Unknown") {
                HStack(spacing: 8) {
                    if load != nil {
                        Button("Clear") { load = nil }.stitch(.bodyMedium13).foregroundStyle(Stitch.accentPrimary)
                    }
                    StitchStepperButtons(decrement: { stepLoad(up: false) }, increment: { stepLoad(up: true) })
                }
            }
            StitchField("Completed reps", value: "\(reps)") {
                StitchStepperButtons(decrement: { reps = max(0, reps - 1) }, increment: { reps = min(1000, reps + 1) })
            }
            StitchSectionLabel("Reps in reserve", meta: "Optional · none = unknown")
            HStack(spacing: 10) {
                ForEach(0...4, id: \.self) { value in
                    Button(value == 4 ? "4+" : "\(value)") { rir = rir == value ? nil : value }
                        .buttonStyle(.stitch(rir == value ? .primary : .secondary))
                        .accessibilityLabel(value == 4 ? "4 or more reps in reserve" : "\(value) reps in reserve")
                }
            }
            StitchFootnote("Log what happened. Zero reps is a valid attempted set. Unknown load or effort stays unknown. 4+ is recorded as 4.")
            Button("Save set") { save() }.buttonStyle(.stitch())
        }
        .stitchSheet("Adjust this set") { dismiss() }
        .onAppear {
            load = slot.load
            reps = slot.targets.indices.contains(workingIndex) ? slot.targets[workingIndex] : slot.lowerReps
        }
    }
    /// Moves to the neighbouring confirmed equipment step when one exists, else by the unit's usual plate.
    private func stepLoad(up: Bool) {
        let loads = slot.equipment.availableLoads.sorted()
        let current = load ?? slot.load ?? 0
        if let next = up ? loads.first(where: { $0 > current + 0.0001 }) : loads.last(where: { $0 < current - 0.0001 }) {
            load = next
        } else {
            let plate: Double = slot.equipment.unit == .kg ? 2.5 : 5
            load = max(0, current + (up ? plate : -plate))
        }
    }
    private func save() {
        let setKind: SetKind = kind == .working ? .working : kind == .warmUp ? .warmUp : .extra
        let index = setKind == .working ? workingIndex : (store.state.activeSession?.logs.count ?? 0)
        store.perform({ try $0.saveSet(sessionID: sessionID, slotID: slot.id, index: index, kind: setKind, load: load,
                                       reps: reps, rir: rir, logID: logID, operationID: operationID) }) { _ in dismiss() }
    }
}

/// ADR-015: describe a set in words ("bench 80 for 8, one left"). Apple's on-device model drafts it,
/// Python keeps only the numbers the athlete said, and nothing is saved until the athlete taps Save.
struct SpokenSetSheet: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    @State private var text = ""
    @State private var reading: SetReading?
    @State private var isReading = false
    @State private var failure: String?
    @State private var logID = UUID()
    @State private var operationID = UUID()
    var body: some View {
        Group {
            VStack(alignment: .leading, spacing: 4) {
                Text("What did you do?").stitch(.monoLabel).textCase(.uppercase).foregroundStyle(Stitch.textMuted)
                TextField("8 reps at 20, two left", text: $text, axis: .vertical)
                    .stitch(.monoBody).foregroundStyle(Stitch.textPrimary)
                    .onChange(of: text) {
                        reading = nil
                        failure = nil
                    }
            }
            .padding(.horizontal, 16).padding(.vertical, 14).glass(radius: 8)
            Button(isReading ? "Reading…" : "Read") { read() }
                .buttonStyle(.stitch(.secondary))
                .disabled(isReading || text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            if let failure {
                StitchNotice("Couldn't read that", body: failure, tone: .warn)
            }
            if let preview = reading?.preview {
                StitchCard(preview.name, body: Self.summary(preview), tone: .accent)
                Button("Save set") { save(preview) }.buttonStyle(.stitch())
            } else if let question = reading?.question {
                StitchNotice("Say a bit more", body: question, tone: .warn)
            }
            if let ignored = reading?.ignored, !ignored.isEmpty {
                StitchFootnote("Not recorded because you didn't say it: \(ignored.map(Self.label).joined(separator: ", ")).")
            }
            StitchFootnote("Read on this iPhone by Apple's on-device model. Only numbers you said are kept, so unknown load or effort stays unknown. Nothing is saved until you tap Save.")
        }
        .stitchSheet("Log in words") { dismiss() }
    }
    /// The model drafts the set on device, then the core checks the draft against the athlete's words.
    private func read() {
        guard let session = store.state.activeSession else { return }
        let words = text
        let names = session.plan.slots.map { store.name($0.exerciseID) }
        isReading = true
        failure = nil
        Task { @MainActor in
            do {
                let draft = try await OnDeviceSetReader.draft(from: words, exerciseNames: names)
                isReading = false
                store.perform({ try $0.readSet(text: words, draft: draft) }) { reading = $0 }
            } catch {
                // Shown in the sheet: the app-wide alert would close it. Every other way to log still works.
                isReading = false
                failure = "The on-device model is unavailable right now. Log this set with the buttons instead."
            }
        }
    }
    private func save(_ preview: SetPreview) {
        store.perform({ try $0.saveSet(sessionID: preview.sessionID, slotID: preview.slotID, index: preview.index,
                                       kind: preview.kind, load: preview.load, reps: preview.reps, rir: preview.rir,
                                       logID: logID, operationID: operationID) }) { _ in dismiss() }
    }
    static func summary(_ preview: SetPreview) -> String {
        let set = preview.kind == .working ? "Set \(preview.index + 1)" : preview.kind == .warmUp ? "Warm-up" : "Extra set"
        let load = preview.load.map { "\(number($0)) \(preview.unit.rawValue)" } ?? "unknown load"
        return "\(set) · \(preview.reps) reps @ \(load) · \(preview.rir.map { "RIR \($0)" } ?? "RIR —")"
    }
    static func label(_ field: String) -> String {
        switch field {
        case "rir": return "reps in reserve"
        case "exercise": return "the exercise it guessed"
        default: return field
        }
    }
}

/// P11: finish the session. The reason is optional; unlogged sets are omissions, not zeros.
struct FinishSheet: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    let onFinished: (UUID) -> Void
    @State private var reason: OmissionReason = .unspecified
    var body: some View {
        Group {
            Menu {
                Picker("Reason", selection: $reason) {
                    ForEach(OmissionReason.allCases, id: \.self) { Text(Self.label($0)).tag($0) }
                }
            } label: {
                StitchField("Reason for omitted work (optional)", value: Self.label(reason)) {
                    Image(systemName: "chevron.right").foregroundStyle(Stitch.textMuted)
                }
            }
            Text("Unlogged sets stay omitted, not zero-strength records. A partial session is saved as ended early. You return to Today with a summary card.")
                .stitch(.body15).foregroundStyle(Stitch.textSecondary)
            Button("Save session") {
                guard let id = store.state.activeSession?.id else { return }
                store.perform({ try $0.finish(reason: reason) }) { _ in onFinished(id) }
            }
            .buttonStyle(.stitch())
        }
        .stitchSheet("Finish") { dismiss() }
    }
    static func label(_ reason: OmissionReason) -> String {
        switch reason {
        case .time: return "Time"
        case .equipment: return "Equipment"
        case .userChoice: return "My choice"
        case .pain: return "Pain"
        case .interruption: return "Interruption"
        case .unspecified: return "Unspecified"
        }
    }
}


/// ADR-021: "Plates: 25 + 15 + 1.25 per side" for a barbell slot with a known load, once the athlete
/// has entered their bar and plates in Settings. The arithmetic runs in the core, off the main thread.
struct PlateLine: View {
    @EnvironmentObject private var store: AppStore
    let slot: Prescription
    @State private var text: String?
    var body: some View {
        Group {
            if let text { Text(text).stitch(.body13).foregroundStyle(Stitch.textSecondary) }
        }
        .task(id: slot.load) { text = await line() }
    }
    private func line() async -> String? {
        guard slot.equipment.basis == .total, let load = slot.load, let service = store.service,
              service.library.exercise(slot.exerciseID)?.equipmentKind == "barbell",
              let saved = PlateSettings.saved else { return nil }
        let unit = slot.equipment.unit.rawValue
        return await Task.detached(priority: .userInitiated) { () -> String? in
            guard let answer = try? service.plates(load: load, bar: saved.bar, plates: saved.plates) else { return nil }
            let side = answer.perSide.isEmpty ? "just the bar" : answer.perSide.map(number).joined(separator: " + ") + " per side"
            return answer.exact ? "Plates: \(side)" : "Plates: \(side) = \(number(answer.total)) \(unit) (closest you can load)"
        }.value
    }
}
