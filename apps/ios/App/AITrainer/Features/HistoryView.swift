import SwiftUI
import AITrainerCore

struct HistoryView: View {
    @EnvironmentObject private var store: AppStore
    var body: some View {
        List {
            if store.state.sessions.isEmpty {
                ContentUnavailableView("Your history starts here", systemImage: "calendar.badge.clock", description: Text("Recorded sets will appear after your first workout. No sample performance is preloaded."))
            }
            ForEach(store.state.sessions.sorted { $0.startedAt > $1.startedAt }) { session in
                NavigationLink { SessionDetailView(sessionID: session.id) } label: {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(session.plan.name).font(.headline)
                        Text(session.startedAt.formatted(date: .abbreviated, time: .shortened)).font(.subheadline)
                        Text("\(session.status.rawValue) · \(session.completeWorkingSets) working sets").font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
        }.navigationTitle("History")
    }
}
struct SessionDetailView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    let sessionID: UUID
    @State private var selected: SetLog?
    @State private var confirmDelete = false
    var body: some View {
        List {
            if let session = store.state.sessions.first(where: { $0.id == sessionID }) {
                Section("Planned versus recorded") {
                    Text("Original: \(session.originalPlan.slots.reduce(0) { $0 + $1.workingSets }) working sets")
                    Text("Accepted session: \(session.plan.slots.reduce(0) { $0 + $1.workingSets }) working sets")
                    Text("Recorded: \(session.completeWorkingSets); omitted: \(session.omissions.count)")
                    if session.plan.modified { Text("Modified session - not original progression evidence").font(.footnote) }
                }
                ForEach(session.plan.slots) { slot in
                    Section(store.name(slot.exerciseID)) {
                        ForEach(session.logs.filter { $0.prescriptionID == slot.id }) { log in
                            Button { selected = log } label: {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("\(log.kind.rawValue): \(log.reps) reps · \(log.load.map(number) ?? "unknown") \(log.unit.rawValue)")
                                    Text("\(log.basis.label) · RIR \(log.rir.map(String.init) ?? "unknown") · revision \(log.revision)").font(.caption)
                                    if log.conflicted { Label("Conflict requires review", systemImage: "exclamationmark.triangle") }
                                }
                            }
                        }
                    }
                }
                ForEach(store.state.conflicts.filter { $0.sessionID == sessionID }) { conflict in
                    Section("Resolve competing edits") {
                        Text("Current: \(conflict.current.reps) reps. Incoming: \(conflict.incoming.reps) reps.")
                        Button("Keep current record") { store.perform { try $0.resolveConflict(id: conflict.id, useIncoming: false) } }
                        Button("Use incoming correction") { store.perform { try $0.resolveConflict(id: conflict.id, useIncoming: true) } }
                    }
                }
                if !session.active {
                    Button("Delete this session", role: .destructive) { confirmDelete = true }
                }
            }
        }.navigationTitle("Session details")
        .sheet(item: $selected) { log in CorrectionView(sessionID: sessionID, original: log) }
        .confirmationDialog("Delete this session and dependent evidence?", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("Delete session", role: .destructive) {
                if store.perform({ try $0.deleteSession(id: sessionID) }) { dismiss() }
            }
        }
    }
}
struct CorrectionView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    let sessionID: UUID
    let original: SetLog
    @State private var reps = ""
    @State private var load = ""
    @State private var rir = ""
    var body: some View {
        NavigationStack {
            Form {
                Text("Correct the actual record. Unapplied recommendations using old evidence will expire.")
                TextField("Load in \(original.unit.rawValue)", text: $load).keyboardType(.decimalPad)
                TextField("Reps", text: $reps).keyboardType(.numberPad)
                TextField("RIR (optional)", text: $rir).keyboardType(.numberPad)
                Button("Save correction") {
                    if store.perform({ service in
                        guard let count = Int(reps), rir.isEmpty || Int(rir) != nil else { throw TrainerError.invalid("Check the reps and effort values.") }
                        let applied = try service.correctSet(sessionID: sessionID, logID: original.id, expectedRevision: original.revision,
                            load: try parseOptionalNumber(load), reps: count, rir: rir.isEmpty ? nil : Int(rir))
                        if !applied { store.errorMessage = "Another edit exists. Review both versions in the session details." }
                    }) { dismiss() }
                }
            }.scrollDismissesKeyboard(.interactively)
                .navigationTitle("Correct a set").toolbar { Button("Cancel") { dismiss() } }
                .onAppear { reps = String(original.reps); load = original.load.map { String($0) } ?? ""; rir = original.rir.map(String.init) ?? "" }
        }
    }
}
