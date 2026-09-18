import SwiftUI
import AITrainerCore

private struct SetEntry: Identifiable {
    let id = UUID()
    let sessionID: UUID
    let prescription: Prescription
    let index: Int
    let kind: SetKind
}
struct WorkoutView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    @State private var entry: SetEntry?
    @State private var showFinish = false
    @State private var omissionReason: OmissionReason = .unspecified
    var body: some View {
        Group {
            if let session = store.state.activeSession {
                List {
                    Section {
                        PhaseNotice(title: "Accepted plan is pinned", detail: "No automatic mid-set escalation. The fixture does not supply approved technique or warm-up coaching.")
                        Text("Status: \(session.status.rawValue) · \(session.completeWorkingSets) working sets recorded")
                        if let end = session.restEndsAt {
                            TimelineView(.periodic(from: .now, by: 1)) { context in
                                let remaining = max(0, Int(ceil(end.timeIntervalSince(context.date))))
                                Label(remaining == 0 ? "Rest timer complete" : String(format: "Rest %02d:%02d", remaining / 60, remaining % 60), systemImage: "timer")
                                    .font(.title2.monospacedDigit())
                            }
                        }
                    }
                    ForEach(session.plan.slots) { slot in
                        Section(store.name(slot.exerciseID)) {
                            Text("Target: \(slot.load.map(number) ?? "unknown") \(slot.equipment.unit.rawValue) · \(slot.equipment.basis.label)")
                            ForEach(0..<slot.workingSets, id: \.self) { index in
                                if let log = session.logs.first(where: { $0.prescriptionID == slot.id && $0.index == index && $0.kind == .working }) {
                                    Label("Set \(index + 1): \(log.reps) reps at \(log.load.map(number) ?? "unknown") \(log.unit.rawValue)", systemImage: "checkmark.circle.fill")
                                } else {
                                    Button("Log set \(index + 1) · target \(slot.targets[index]) reps") {
                                        entry = SetEntry(sessionID: session.id, prescription: slot, index: index, kind: .working)
                                    }.disabled(session.status == .paused)
                                }
                            }
                            Menu("Additional log") {
                                Button("Warm-up set") { entry = SetEntry(sessionID: session.id, prescription: slot, index: session.logs.count, kind: .warmUp) }
                                Button("Extra set - not prescribed") { entry = SetEntry(sessionID: session.id, prescription: slot, index: session.logs.count, kind: .extra) }
                            }.disabled(session.status == .paused)
                            Button("Report pain and pause guidance", role: .destructive) {
                                store.perform { try $0.reportPain(exerciseID: slot.exerciseID) }
                            }
                        }
                    }
                    Section {
                        Button(session.status == .paused ? "Resume session" : "Pause session") {
                            store.perform { try $0.setPaused(session.status != .paused) }
                        }
                        Button("Finish / end session") { showFinish = true }
                    }
                }
            } else {
                ContentUnavailableView("Session saved", systemImage: "checkmark.circle", description: Text("Review your actual performance in History. Next-session proposals are available on Today."))
            }
        }
        .navigationTitle("Workout")
        .sheet(item: $entry) { selection in SetLogView(sessionID: selection.sessionID, slot: selection.prescription, setIndex: selection.index, kind: selection.kind) }
        .sheet(isPresented: $showFinish) {
            NavigationStack {
                Form {
                    Picker("Reason for any omitted work", selection: $omissionReason) {
                        ForEach(OmissionReason.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                    }
                    Text("Unlogged working sets remain omitted, not zero-strength records. A partially logged session is saved as ended early.")
                    Button("Save session summary") {
                        if store.perform({ try $0.finish(reason: omissionReason) }) { showFinish = false; dismiss() }
                    }
                }.navigationTitle("End session").toolbar { Button("Cancel") { showFinish = false } }
            }
        }
    }
}
struct SetLogView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    let sessionID: UUID
    let slot: Prescription
    let setIndex: Int
    let kind: SetKind
    @State private var load = ""
    @State private var reps = ""
    @State private var rir = ""
    @State private var operationID = UUID()
    @State private var logID = UUID()
    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("\(kind.rawValue) · \(slot.equipment.basis.label) · \(slot.equipment.unit.rawValue)")
                    TextField("Actual load (blank = unknown)", text: $load).keyboardType(.decimalPad)
                    TextField("Completed reps", text: $reps).keyboardType(.numberPad)
                    TextField("Estimated reps in reserve, 0-10 (optional)", text: $rir).keyboardType(.numberPad)
                } header: { Text(store.name(slot.exerciseID)) } footer: { Text("Log what happened, not just the target. Zero completed reps is a valid attempted set. Unknown effort stays unknown.") }
                Button("Save set locally") {
                    if store.perform({ service in
                        guard let count = Int(reps) else { throw TrainerError.invalid("Enter actual completed reps.") }
                        let effort: Int?
                        if rir.isEmpty { effort = nil }
                        else if let parsed = Int(rir) { effort = parsed }
                        else { throw TrainerError.invalid("Enter whole-number RIR or leave it blank.") }
                        let log = SetLog(id: logID, operationID: operationID, prescription: slot, index: setIndex, kind: kind,
                                         load: try parseOptionalNumber(load), reps: count, rir: effort)
                        try service.saveSet(log, sessionID: sessionID)
                    }) { dismiss() }
                }.buttonStyle(.borderedProminent)
            }.navigationTitle("Record performance").toolbar { Button("Cancel") { dismiss() } }
                .onAppear { load = slot.load.map { String($0) } ?? "" }
        }
    }
}
