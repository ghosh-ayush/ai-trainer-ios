import SwiftUI
import AITrainerCore

/// P14 Progress (was History): recorded values per exercise, then every session newest first.
struct ProgressTabView: View {
    @EnvironmentObject private var store: AppStore
    var body: some View {
        TabRoot("Progress") {
            if store.state.sessions.isEmpty {
                StitchCard("Your history starts here", body: "Recorded sets appear after your first workout. No sample performance is preloaded.")
            } else {
                ForEach(store.progress, id: \.exerciseID) { block in
                    StitchSectionLabel(block.name, meta: "Recorded · last \(block.entries.count) session\(block.entries.count == 1 ? "" : "s")")
                    if let load = block.load {
                        StitchStat(block.unchangedSessions > 1 ? "Working load · unchanged for \(block.unchangedSessions) sessions" : "Working load · latest session",
                                   value: number(load), unit: block.unit.rawValue)
                    }
                    ForEach(block.entries, id: \.sessionID) { entry in
                        StitchKeyValue(entry.date.formatted(.dateTime.month(.abbreviated).day()), value: entry.summary)
                    }
                }
                if !store.progress.isEmpty {
                    StitchNotice("Recorded values only", body: "These are the sets you confirmed. Nothing here is estimated or projected.")
                }
                StitchSectionLabel("Recorded sessions", meta: "Newest first")
                ForEach(store.state.sessions.sorted { $0.startedAt > $1.startedAt }) { session in
                    NavigationLink { SessionDetailView(sessionID: session.id) } label: {
                        StitchListRow(session.plan.name,
                                      subtitle: "\(session.startedAt.formatted(date: .abbreviated, time: .shortened)) · \(session.status.rawValue) · \(session.completeWorkingSets) working sets",
                                      symbol: "figure.strengthtraining.traditional")
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }
}

/// P15 Session details: planned versus recorded, each set (tap to correct), conflicts, delete.
struct SessionDetailView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    let sessionID: UUID
    @State private var selected: SetLog?
    @State private var confirmDelete = false
    var body: some View {
        DetailScreen("Session details") {
            if let session = store.state.sessions.first(where: { $0.id == sessionID }) {
                StitchSectionLabel("Planned versus recorded", meta: session.startedAt.formatted(date: .abbreviated, time: .shortened))
                StitchCard {
                    StitchKeyValue("Original plan", value: "\(session.originalPlan.slots.reduce(0) { $0 + $1.workingSets }) working sets")
                    StitchKeyValue("Accepted session", value: "\(session.plan.slots.reduce(0) { $0 + $1.workingSets }) working sets")
                    StitchKeyValue("Recorded", value: "\(session.completeWorkingSets)")
                    StitchKeyValue("Omitted", value: "\(session.omissions.count)")
                    if session.plan.modified { StitchFootnote("Modified session — not original progression evidence.") }
                }
                ForEach(session.plan.slots) { slot in
                    StitchSectionLabel(store.name(slot.exerciseID), meta: slot.equipment.basis.label)
                    ForEach(session.logs.filter { $0.prescriptionID == slot.id }) { log in
                        Button { selected = log } label: { SetLogRow(log: log) }.buttonStyle(.plain)
                    }
                }
                ForEach(store.state.conflicts.filter { $0.sessionID == sessionID }) { conflict in
                    ConflictCard(conflict: conflict)
                }
                if !session.active {
                    Button("Delete this session", role: .destructive) { confirmDelete = true }.buttonStyle(.stitch(.destructive))
                }
            }
        }
        .sheet(item: $selected) { CorrectionSheet(sessionID: sessionID, original: $0) }
        .confirmationDialog("Delete this session and dependent evidence?", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("Delete session", role: .destructive) {
                if store.perform({ try $0.deleteSession(id: sessionID) }) { dismiss() }
            }
        }
    }
}

private struct SetLogRow: View {
    let log: SetLog
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("\(log.kind.rawValue) · \(log.reps) reps · \(log.load.map(number) ?? "unknown") \(log.unit.rawValue)")
                    .stitch(.monoBody).foregroundStyle(Stitch.textPrimary)
                Spacer()
                Image(systemName: "pencil").foregroundStyle(Stitch.textMuted)
            }
            Text("\(log.basis.label) · RIR \(log.rir.map(String.init) ?? "unknown") · revision \(log.revision)")
                .stitch(.body13).foregroundStyle(Stitch.textSecondary)
            if log.conflicted {
                Label("Conflict requires review", systemImage: "exclamationmark.triangle.fill").stitch(.bodyMedium13).foregroundStyle(Stitch.warnPrimary)
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 12)
        .glass(log.conflicted ? .warn : .default, radius: 8, fill: Stitch.glassInset)
        .accessibilityHint("Correct this set")
    }
}

/// P17 Resolve conflict: two versions of one set; the athlete picks, the other is kept in the audit.
private struct ConflictCard: View {
    @EnvironmentObject private var store: AppStore
    let conflict: Conflict
    var body: some View {
        StitchSectionLabel("Resolve competing edits")
        StitchCard(tone: .warn) {
            StitchKeyValue("Current", value: "\(conflict.current.reps) reps · \(conflict.current.load.map(number) ?? "unknown")")
            StitchKeyValue("Incoming", value: "\(conflict.incoming.reps) reps · \(conflict.incoming.load.map(number) ?? "unknown")")
        }
        Button("Keep current record") { store.perform { try $0.resolveConflict(id: conflict.id, useIncoming: false) } }
            .buttonStyle(.stitch(.secondary))
        Button("Use incoming correction") { store.perform { try $0.resolveConflict(id: conflict.id, useIncoming: true) } }
            .buttonStyle(.stitch())
    }
}

/// P16 Correct set: edits the record; proposals that relied on the old value expire.
struct CorrectionSheet: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    let sessionID: UUID
    let original: SetLog
    @State private var reps = ""
    @State private var load = ""
    @State private var rir = ""
    var body: some View {
        Group {
            Text("Correct the actual record. Unapplied recommendations using old evidence will expire.")
                .stitch(.body15).foregroundStyle(Stitch.textSecondary)
            entry("Load · \(original.unit.rawValue) (blank = unknown)", text: $load, keyboard: .decimalPad)
            entry("Reps", text: $reps, keyboard: .numberPad)
            entry("RIR (optional)", text: $rir, keyboard: .numberPad)
            Button("Save correction") { save() }.buttonStyle(.stitch())
        }
        .stitchSheet("Correct a set") { dismiss() }
        .onAppear { reps = String(original.reps); load = original.load.map { String($0) } ?? ""; rir = original.rir.map(String.init) ?? "" }
    }
    private func entry(_ label: String, text: Binding<String>, keyboard: UIKeyboardType) -> some View {
        StitchField(label, value: "") {
            TextField("Unknown", text: text).keyboardType(keyboard).stitch(.monoBody)
                .multilineTextAlignment(.trailing).foregroundStyle(Stitch.textPrimary)
        }
    }
    private func save() {
        let didSave = store.perform { service in
            guard let count = Int(reps), rir.isEmpty || Int(rir) != nil else { throw TrainerError.invalid("Check the reps and effort values.") }
            let applied = try service.correctSet(sessionID: sessionID, logID: original.id, expectedRevision: original.revision,
                                                 load: try parseOptionalNumber(load), reps: count, rir: rir.isEmpty ? nil : Int(rir))
            if !applied { store.errorMessage = "Another edit exists. Review both versions in the session details." }
        }
        if didSave { dismiss() }
    }
}
