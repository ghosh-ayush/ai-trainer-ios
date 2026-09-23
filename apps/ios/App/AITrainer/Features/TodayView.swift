import SwiftUI
import AITrainerCore

struct TodayView: View {
    @EnvironmentObject private var store: AppStore
    @State private var selectedLoad: Prescription?
    @State private var selectedSwap: Prescription?
    @State private var showCheckIn = false
    @State private var showShorten = false
    @State private var showSchedule = false
    @State private var confirmSkip = false
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text(Date.now.formatted(date: .complete, time: .omitted)).font(.subheadline).foregroundStyle(.secondary)
                PhaseNotice(title: "P1 - local training", detail: "Sample policies. Recorded performance, proposed changes, and accepted plans remain separate.")
                if let session = store.state.activeSession {
                    Panel {
                        Label(session.status == .paused ? "Workout paused" : "Workout in progress", systemImage: "figure.strengthtraining.traditional").font(.headline)
                        Text("\(session.completeWorkingSets) working sets recorded locally")
                        NavigationLink("Open workout") { WorkoutView() }.buttonStyle(.borderedProminent)
                    }
                } else if let plan = store.state.nextPlan {
                    Panel {
                        Text(plan.name).font(.title2.bold())
                        Text("\(plan.estimatedMinutes) fixture minutes · \(plan.slots.count) exercises · revision \(plan.revision)").foregroundStyle(.secondary)
                        if plan.modified { Label("Temporary session adjustment", systemImage: "arrow.triangle.branch").font(.caption) }
                        if let date = plan.scheduledDate { Text("Scheduled: \(date.formatted(date: .abbreviated, time: .shortened))") }
                        Button("Check in & start") { showCheckIn = true }.buttonStyle(.borderedProminent)
                    }
                    ForEach(plan.slots) { slot in
                        Panel {
                            Text(store.name(slot.exerciseID)).font(.headline)
                            Text("\(slot.targets.map(String.init).joined(separator: " / ")) reps · \(slot.equipment.basis.label)")
                            Text(slot.load.map { "\(number($0)) \(slot.equipment.unit.rawValue)" } ?? "Working load not set")
                                .foregroundStyle(slot.load == nil ? .secondary : .primary)
                            HStack {
                                Button("Load & equipment") { selectedLoad = slot }
                                Spacer()
                                Menu {
                                    Button("Review progression") { store.request(.progression(slot.id)) }
                                    Button("Curated swap") { selectedSwap = slot }
                                    Button("Report pain / pause guidance", role: .destructive) { store.perform { try $0.reportPain(exerciseID: slot.exerciseID) } }
                                } label: { Image(systemName: "ellipsis.circle").font(.title2) }.accessibilityLabel("Options for \(store.name(slot.exerciseID))")
                            }
                        }
                    }
                    HStack {
                        Button("Shorten") { showShorten = true }
                        Spacer(); Button("Reschedule") { showSchedule = true }
                        Spacer(); Button("Skip") { confirmSkip = true }
                    }.buttonStyle(.bordered)
                }
                ForEach(store.state.recommendations.filter { $0.status == .proposed }) { recommendation in
                    RecommendationPanel(recommendation: recommendation)
                }
            }.padding()
        }
        .background(Color(uiColor: .systemGroupedBackground)).navigationTitle("Today")
        .sheet(item: $selectedLoad) { LoadSetupView(slot: $0) }
        .sheet(item: $selectedSwap) { SwapView(slot: $0) }
        .sheet(isPresented: $showCheckIn) { CheckInView() }
        .sheet(isPresented: $showShorten) { ShortenView() }
        .sheet(isPresented: $showSchedule) { ScheduleView() }
        .confirmationDialog("Skip this session? Work will not be added to the next session.", isPresented: $confirmSkip, titleVisibility: .visible) {
            Button("Skip session", role: .destructive) { store.perform { try $0.skip() } }
        }
    }
}
struct RecommendationPanel: View {
    @EnvironmentObject private var store: AppStore
    let recommendation: Recommendation
    var body: some View {
        Panel {
            Label("Review a proposed change", systemImage: "sparkles").font(.headline)
            Text(recommendation.decision.explanation)
            if let after = recommendation.decision.after {
                ForEach(after.slots) { slot in
                    Text("\(store.name(slot.exerciseID)): \(slot.load.map(number) ?? "unknown") \(slot.equipment.unit.rawValue), reps \(slot.targets.map(String.init).joined(separator: "/"))")
                        .font(.subheadline)
                }
            }
            DisclosureGroup("Why this suggestion?") {
                Text("Reason: \(recommendation.decision.reason)\nPolicy: \(recommendation.policyVersion)\nEvidence: \(recommendation.decision.evidence.count) recorded sets\nApplied only after acceptance and revalidation.")
                    .font(.caption).frame(maxWidth: .infinity, alignment: .leading)
            }
            HStack {
                Button("Accept") { store.perform { try $0.acceptRecommendation(id: recommendation.id) } }.buttonStyle(.borderedProminent)
                Menu("Keep current") {
                    Button("Prefer current plan") { store.perform { try $0.rejectRecommendation(id: recommendation.id, reason: "prefer_current") } }
                    Button("Equipment unavailable today") { store.perform { try $0.rejectRecommendation(id: recommendation.id, reason: "equipment_unavailable") } }
                }.buttonStyle(.bordered)
            }
        }
    }
}
struct LoadSetupView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    let slot: Prescription
    @State private var load = ""
    @State private var options = ""
    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("\(slot.equipment.basis.label) in \(slot.equipment.unit.rawValue)")
                    TextField("Known working load; blank means unknown", text: $load).keyboardType(.decimalPad)
                    TextField("Available loads, separated by commas", text: $options).keyboardType(.numbersAndPunctuation)
                } header: { Text(store.name(slot.exerciseID)) } footer: { Text("Use your own known equipment values, for example 100, 105, 110. Do not transfer weights between different machines. This is a manual confirmation, not an AI strength estimate.") }
                Button("Confirm equipment and load") {
                    if store.perform({ service in
                        let value = try parseOptionalNumber(load)
                        let choices: [Double] = try options.split(separator: ",").map { part in
                            guard let number = try parseOptionalNumber(String(part)) else { throw TrainerError.invalid("Check available load values.") }
                            return number
                        }
                        try service.configureLoad(slotID: slot.id, load: value, options: choices)
                    }) { dismiss() }
                }
            }.navigationTitle("Load setup").toolbar { Button("Cancel") { dismiss() } }
                .onAppear { load = slot.load.map { String($0) } ?? ""; options = slot.equipment.availableLoads.map { String($0) }.joined(separator: ", ") }
        }
    }
}
struct CheckInView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    @State private var checkIn = CheckIn()
    @State private var minutes = 60
    var body: some View {
        NavigationStack {
            Form {
                Section("This session only") {
                    Picker("Energy", selection: $checkIn.energy) {
                        Text("Unknown").tag(String?.none)
                        ForEach(["Low", "Typical", "High"], id: \.self) { Text($0).tag(Optional($0)) }
                    }
                    Picker("Soreness", selection: $checkIn.soreness) {
                        Text("Unknown").tag(String?.none)
                        ForEach(["None reported", "Some soreness", "High soreness"], id: \.self) { Text($0).tag(Optional($0)) }
                    }
                    Stepper("\(minutes) available minutes", value: $minutes, in: 5...180, step: 5)
                    Toggle("I am reporting pain", isOn: $checkIn.painReported)
                }
                if checkIn.painReported {
                    Text("Pause training guidance. Report the affected activity from Today; this app does not diagnose the concern or clear an alternative exercise.")
                } else {
                    Text("Energy and soreness do not silently change the plan. Use Shorten or Reschedule to request a preview.").font(.footnote)
                }
                Button("Start accepted workout") {
                    checkIn.minutes = minutes; checkIn.occurredAt = Date()
                    if store.perform({ try $0.start(checkIn: checkIn) }) { dismiss() }
                }.disabled(checkIn.painReported)
            }.navigationTitle("Before you train").toolbar { Button("Cancel") { dismiss() } }
                .onAppear { minutes = max(60, store.state.nextPlan?.estimatedMinutes ?? 60) }
        }
    }
}
struct ShortenView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    @State private var minutes = 35
    var body: some View {
        NavigationStack {
            Form {
                Stepper("\(minutes) available minutes", value: $minutes, in: 5...120, step: 5)
                Text("Optional slots can be removed. The fixture will not compress required work, warm-up, or rest.")
                Button("Preview shorter session") { store.request(.shorten(minutes)); dismiss() }
            }.navigationTitle("Adjust session").toolbar { Button("Cancel") { dismiss() } }
        }
    }
}
struct SwapView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    let slot: Prescription
    var body: some View {
        NavigationStack {
            List {
                Text("Alternatives are directional library entries, not a claim of identical loading or safety. The final preview checks your equipment and exclusions.")
                ForEach(store.service?.library.exercise(slot.exerciseID)?.alternatives ?? [], id: \.self) { id in
                    Button(store.name(id)) { store.request(.substitute(slot.id, id)); dismiss() }
                }
            }.navigationTitle("Curated alternatives").toolbar { Button("Cancel") { dismiss() } }
        }
    }
}
struct ScheduleView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    @State private var date = Date().addingTimeInterval(86400)
    var body: some View {
        NavigationStack {
            Form {
                DatePicker("Move session to", selection: $date, in: Date()...)
                Text("This moves the next session only. It does not change the sequence or add missed work.")
                Button("Preview reschedule") { store.request(.reschedule(date)); dismiss() }
            }.navigationTitle("Reschedule").toolbar { Button("Cancel") { dismiss() } }
        }
    }
}
