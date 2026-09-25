import SwiftUI
import AITrainerCore

/// P03 Today: the next session, one-tap Start, adjustments as chips, and each slot with its
/// needs-state or proposal underneath. Coach, the check-in screen and the proposal panels fold in here.
struct TodayView: View {
    @EnvironmentObject private var store: AppStore
    @State private var loadSlot: Prescription?
    @State private var swapSlot: Prescription?
    @State private var showLessTime = false
    @State private var showMoveDay = false
    @State private var showPain = false
    @State private var confirmSkip = false
    @State private var openWorkout = false
    @State private var showStatus = false
    var body: some View {
        ScrollViewReader { proxy in
            TabRoot("Today") {
                Text(Date.now.formatted(date: .complete, time: .omitted)).stitch(.bodyMedium15).foregroundStyle(Stitch.textSecondary)
                StatusBanner(onChoose: { showStatus = true })
                if let session = store.state.activeSession {
                    activeHero(session)
                } else if let plan = store.state.nextPlan {
                    if let summary = finishedSummary { summary }
                    nextSessionHero(plan)
                    ForEach(heroProposals, id: \.recommendationID) { ProposalBlock(proposal: $0).id($0.recommendationID) }
                    if let adjusted = adjustedForToday(plan) { adjusted }
                }
                if let plan = store.state.activeSession?.plan ?? store.state.nextPlan {
                    StitchSectionLabel("Prescribed sequence", meta: "\(plan.slots.count) slots")
                    ForEach(Array(plan.slots.enumerated()), id: \.element.id) { index, slot in
                        SlotCard(slot: slot, position: index + 1, onLoad: { loadSlot = slot }, onSwap: { swapSlot = slot }, onPain: { showPain = true })
                        if store.state.activeSession != nil, index == 0 {
                            StitchCard("Finish the current session first", body: "Plan changes wait until the session ends. Open workout to continue.")
                        }
                        ForEach(store.today.slots.filter { $0.slotID == slot.id }, id: \.reason) { status in
                            SlotStatusCard(status: status, onLoad: { loadSlot = slot }, onSwap: { swapSlot = slot })
                        }
                        ForEach(store.today.proposals.filter { $0.slotID == slot.id && $0.kind != "shorten" && $0.kind != "reschedule" }, id: \.recommendationID) {
                            ProposalBlock(proposal: $0).id($0.recommendationID)
                        }
                    }
                }
                DietSummaryCard()
                WhatCouldChangeSection()
            }
            .scrollToNewProposal(store.state.recommendations, proxy: proxy)
        }
        .navigationDestination(isPresented: $openWorkout) { WorkoutView() }
        .sheet(item: $loadSlot) { LoadSheet(slot: $0) }
        .sheet(item: $swapSlot) { SwapSheet(slot: $0) }
        .sheet(isPresented: $showLessTime) { LessTimeSheet() }
        .sheet(isPresented: $showMoveDay) { MoveDaySheet() }
        .sheet(isPresented: $showPain) { PainSheet() }
        .sheet(isPresented: $showStatus) { StatusSheet() }
        .confirmationDialog("Skip this session? Work will not be added to the next session.", isPresented: $confirmSkip, titleVisibility: .visible) {
            Button("Skip session", role: .destructive) { store.perform { try $0.skip() } }
        }
    }

    // MARK: Hero states

    private func activeHero(_ session: WorkoutSession) -> some View {
        let planned = session.plan.slots.reduce(0) { $0 + $1.workingSets }
        let timer = session.restEndsAt.map { $0 > .now ? "rest timer running" : "rest complete" } ?? "no rest timer"
        return Group {
            StitchCard("Workout \(session.status == .paused ? "paused" : "in progress") · \(session.completeWorkingSets) of \(planned) sets",
                       body: "Started \(session.startedAt.formatted(date: .omitted, time: .shortened)) · \(timer) · plan pinned until you finish.",
                       tone: .accent)
            NavigationLink { WorkoutView() } label: { Text("Open workout") }.buttonStyle(.stitch())
        }
    }

    private func nextSessionHero(_ plan: SessionPlan) -> some View {
        let confirmed = plan.slots.filter { $0.load != nil }.count
        let when = plan.scheduledDate.map { "Next session · \($0.formatted(date: .abbreviated, time: .shortened))." }
            ?? plan.weekday.map { "Next session · \(Weekday.name($0)) · \(plan.name)." }
            ?? "Next session · today."
        let detail = plan.modified
            ? "Temporary session adjustment · for today only. Revision \(plan.revision)."
            : "\(when) Loads confirmed: \(confirmed) of \(plan.slots.count). Revision \(plan.revision)."
        return Group {
            StitchCard("\(planTitle(plan)) · \(plan.slots.count) exercises · ~\(plan.estimatedMinutes) min", body: detail, tone: .accent)
            Button(store.justFinishedSessionID == nil ? "Start" : "Start next session") {
                store.perform({ try $0.start() }) { _ in store.justFinishedSessionID = nil; openWorkout = true }
            }
            .buttonStyle(.stitch())
            HStack(spacing: 8) {
                Button("Less time") { showLessTime = true }.buttonStyle(.stitch(.secondary, compact: true))
                Button("Move day") { showMoveDay = true }.buttonStyle(.stitch(.secondary, compact: true))
            }
            HStack(spacing: 8) {
                Button("Skip") { confirmSkip = true }.buttonStyle(.stitch(.secondary, compact: true))
                Button("I'm in pain") { showPain = true }.buttonStyle(.stitch(.destructive, compact: true))
            }
        }
    }

    /// P03c: the summary card that replaces the old "Session saved" screen.
    private var finishedSummary: StitchCard<StitchCardText>? {
        guard let id = store.justFinishedSessionID, let session = store.state.sessions.first(where: { $0.id == id }) else { return nil }
        let planned = session.plan.slots.reduce(0) { $0 + $1.workingSets }
        let omitted = session.omissions.count
        let reasons = Set(session.omissions.values.map(\.rawValue)).sorted().joined(separator: ", ")
        let omittedText = omitted == 0 ? "Every planned set recorded." : "\(omitted) set\(omitted == 1 ? "" : "s") omitted (\(reasons))."
        return StitchCard("Session saved · \(session.completeWorkingSets) of \(planned) sets recorded",
                          body: "\(omittedText) New proposals appear on the cards below.", tone: .accent)
    }

    /// P03d: names what a temporary adjustment removed or replaced compared with the program's plan.
    private func adjustedForToday(_ plan: SessionPlan) -> StitchCard<StitchCardText>? {
        guard store.state.nextPlanOverride != nil, let program = store.state.program,
              program.plans.indices.contains(program.sequenceIndex) else { return nil }
        let base = program.plans[program.sequenceIndex]
        let current = Set(plan.slots.map(\.exerciseID))
        let removed = base.slots.map(\.exerciseID).filter { !current.contains($0) }.map(store.name)
        guard !removed.isEmpty else { return nil }
        return StitchCard("Adjusted for today", body: "\(removed.joined(separator: ", ")) \(removed.count == 1 ? "is" : "are") omitted for this session only. The original plan returns next time.")
    }

    private var heroProposals: [ProposalCard] {
        store.today.proposals.filter { $0.kind == "shorten" || $0.kind == "reschedule" || $0.kind == "replan" }
    }

    private func planTitle(_ plan: SessionPlan) -> String {
        plan.name.components(separatedBy: " - ").first ?? plan.name
    }
}

// MARK: - Slot card (S/SlotCard)

struct SlotCard: View {
    @EnvironmentObject private var store: AppStore
    let slot: Prescription
    let position: Int
    let onLoad: () -> Void
    let onSwap: () -> Void
    let onPain: () -> Void
    var body: some View {
        StitchCard {
            HStack {
                Text(headline).stitch(.monoLabel).textCase(.uppercase).foregroundStyle(Stitch.textMuted)
                Spacer()
                Menu {
                    Button("Curated swap", systemImage: "arrow.triangle.swap", action: onSwap)
                    Button("Load & equipment", systemImage: "scalemass", action: onLoad)
                    Button("I'm in pain", systemImage: "bandage", role: .destructive, action: onPain)
                } label: {
                    Image(systemName: "ellipsis.circle").foregroundStyle(Stitch.textSecondary).frame(minWidth: 44, minHeight: 28, alignment: .trailing)
                }
                .accessibilityLabel("Options for \(store.name(slot.exerciseID))")
                .disabled(store.state.activeSession != nil)
            }
            Text(store.name(slot.exerciseID)).stitch(.displayH2).foregroundStyle(Stitch.textPrimary)
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Target").stitch(.monoLabel).textCase(.uppercase).foregroundStyle(Stitch.textMuted)
                    Text("\(slot.workingSets) sets × \(slot.targets.map(String.init).joined(separator: " / ")) reps").stitch(.monoBody).foregroundStyle(Stitch.textPrimary)
                    Text(slot.equipment.basis.label).stitch(.body13).foregroundStyle(Stitch.textSecondary)
                }
                Spacer(minLength: 8)
                VStack(alignment: .trailing, spacing: 4) {
                    Text("Working load").stitch(.monoLabel).textCase(.uppercase).foregroundStyle(Stitch.textMuted)
                    Button(action: onLoad) { LoadBox(load: slot.load, unit: slot.equipment.unit) }
                        .buttonStyle(.plain).disabled(store.state.activeSession != nil)
                        .accessibilityLabel(slot.load.map { "Working load \(number($0)) \(slot.equipment.unit.rawValue). Change" } ?? "Working load not set. Set load")
                }
            }
            Button("Load & equipment", action: onLoad).buttonStyle(.stitch(.secondary))
                .disabled(store.state.activeSession != nil)
        }
    }
    private var headline: String {
        let role = store.service?.library.exercise(slot.exerciseID)?.role ?? "exercise"
        return String(format: "Slot %02d · %@", position, role) + (slot.optional ? " · optional" : "")
    }
}

/// The load chip: the confirmed working load, or an explicit "[ not set ]" — never a guess.
struct LoadBox: View {
    let load: Double?
    let unit: MassUnit
    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 4) {
            if let load {
                Text(number(load)).stitch(.monoNumber).foregroundStyle(Stitch.textPrimary)
                Text(unit.rawValue).stitch(.monoSmall).foregroundStyle(Stitch.textMuted)
            } else {
                Text("[ not set ]").stitch(.monoBody).foregroundStyle(Stitch.textMuted)
            }
        }
        .padding(.horizontal, 10).padding(.vertical, 6)
        .background(Stitch.glassDeep, in: RoundedRectangle(cornerRadius: 6, style: .continuous))
    }
}

/// A needs-state computed by the core, with the action it names.
struct SlotStatusCard: View {
    let status: SlotStatus
    let onLoad: () -> Void
    let onSwap: () -> Void
    @State private var keptPaused = false
    var body: some View {
        StitchCard(status.title, body: status.body, tone: StitchTone(name: status.tone))
        if status.action == "swap", !keptPaused {
            HStack(spacing: 8) {
                Button("Swap exercise", action: onSwap).buttonStyle(.stitch(compact: true))
                Button("Keep paused") { keptPaused = true }.buttonStyle(.stitch(.secondary, compact: true))
            }
        }
    }
}

/// A pending proposal: accent card, Accept / Keep current, and the expandable reasoning.
struct ProposalBlock: View {
    @EnvironmentObject private var store: AppStore
    let proposal: ProposalCard
    @State private var showWhy = false
    var body: some View {
        StitchCard(proposal.title, body: proposal.body + " Applies only after you accept.", tone: .accent)
        HStack(spacing: 8) {
            Button("Accept") { store.perform { try $0.acceptRecommendation(id: proposal.recommendationID) } }
                .buttonStyle(.stitch(compact: true))
            Menu {
                Button("Prefer current plan") { reject("prefer_current") }
                Button("Equipment unavailable today") { reject("equipment_unavailable") }
                Button("Other reason") { reject("other") }
            } label: { Text("Keep current  ⌄") }
                .buttonStyle(.stitch(.secondary, compact: true))
        }
        Button(showWhy ? "Hide reasoning" : "Why this suggestion?") { withAnimation { showWhy.toggle() } }
            .buttonStyle(.stitch(.link))
        if showWhy, let recommendation = store.state.recommendations.first(where: { $0.id == proposal.recommendationID }) {
            StitchCard {
                StitchKeyValue("Reason", value: recommendation.decision.reason)
                StitchKeyValue("Policy", value: recommendation.policyVersion)
                StitchKeyValue("Evidence", value: "\(recommendation.decision.evidence.count) recorded sets")
                StitchFootnote("Applied only after acceptance and a fresh re-check against your current records.")
            }
        }
    }
    private func reject(_ reason: String) {
        store.perform { try $0.rejectRecommendation(id: proposal.recommendationID, reason: reason) }
    }
}

extension View {
    /// Scrolls to a proposal as soon as it appears, so it is not hidden below the fold.
    func scrollToNewProposal(_ recommendations: [Recommendation], proxy: ScrollViewProxy) -> some View {
        onChange(of: recommendations.last { $0.status == .proposed }?.id) { _, id in
            guard let id else { return }
            withAnimation { proxy.scrollTo(id, anchor: .top) }
        }
    }
}

// MARK: - Sheets

/// P04: set the working load and the equipment steps it moves in. Clear the load for unknown.
struct LoadSheet: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    let slot: Prescription
    @State private var loadText = ""
    @State private var step: Double = 2.5
    @State private var editList = false
    @State private var listText = ""
    @State private var generated: [Double] = []
    private var steps: [Double] { slot.equipment.unit == .kg ? [2.5, 5] : [5, 10] }
    var body: some View {
        Group {
            StitchSectionLabel(store.name(slot.exerciseID), meta: "\(slot.equipment.basis.label) · \(slot.equipment.unit.rawValue)")
            StitchSectionLabel("Increment", meta: "Your equipment step")
            HStack(spacing: 10) {
                ForEach(steps, id: \.self) { value in
                    Button("\(number(value)) \(slot.equipment.unit.rawValue)") { step = value; editList = false; regenerate() }
                        .buttonStyle(.stitch(!editList && step == value ? .primary : .secondary))
                }
                Button("Stack") { editList = true }.buttonStyle(.stitch(editList ? .primary : .secondary))
            }
            StitchField("Known working load (clear = unknown)", value: "") {
                HStack(spacing: 8) {
                    TextField("Unknown", text: $loadText).keyboardType(.decimalPad).stitch(.monoBody)
                        .multilineTextAlignment(.trailing).frame(maxWidth: 72).foregroundStyle(Stitch.textPrimary)
                        .onChange(of: loadText) { regenerate() }
                    StitchStepperButtons(decrement: { adjust(by: -step) }, increment: { adjust(by: step) })
                }
            }
            if editList {
                StitchSectionLabel("Available loads", meta: "Your list, comma separated")
                TextField("e.g. 15, 17.5, 20", text: $listText).keyboardType(.numbersAndPunctuation).stitch(.monoBody)
                    .padding(14).glass(radius: 8)
            } else {
                StitchSectionLabel("Available loads", meta: "Generated · base ± 10 steps")
                if generated.isEmpty {
                    StitchFootnote("Enter your working load to list the steps around it.")
                } else {
                    ScrollViewReader { proxy in
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 10) {
                                ForEach(generated, id: \.self) { value in
                                    Button(number(value)) { loadText = number(value) }
                                        .buttonStyle(.stitch(Double(loadText) == value ? .primary : .secondary))
                                        .frame(width: 66).id(value)
                                }
                            }
                        }
                        // Open centred on the confirmed load rather than at the bottom of the range.
                        .onChange(of: generated) { if let base = Double(loadText) { proxy.scrollTo(base, anchor: .center) } }
                        .onAppear { if let base = Double(loadText) { proxy.scrollTo(base, anchor: .center) } }
                    }
                }
                Button("Edit the list instead") { listText = generated.map(number).joined(separator: ", "); editList = true }
                    .buttonStyle(.stitch(.link))
            }
            StitchFootnote("Use your own equipment values. Do not transfer loads between machines. The app never estimates your strength.")
            Button("Confirm load") { confirm() }.buttonStyle(.stitch())
        }
        .stitchSheet("Set your load") { dismiss() }
        .onAppear {
            loadText = slot.load.map(number) ?? ""
            step = steps[0]
            if !slot.equipment.availableLoads.isEmpty {
                listText = slot.equipment.availableLoads.map(number).joined(separator: ", ")
            }
            regenerate()
        }
    }
    private func adjust(by delta: Double) {
        let current = Double(loadText) ?? 0
        loadText = number(max(0, current + delta))
    }
    private func regenerate() {
        guard let base = Double(loadText), let service = store.service else { generated = []; return }
        generated = (try? service.loadSteps(base: base, step: step)) ?? []
    }
    private func confirm() {
        store.perform({ service in
            let load = try parseOptionalNumber(loadText)
            let options: [Double]
            if editList {
                options = try listText.split(separator: ",").map { part in
                    guard let value = try parseOptionalNumber(String(part)) else { throw TrainerError.invalid("Check the available load values.") }
                    return value
                }
            } else {
                options = generated
            }
            try service.configureLoad(slotID: slot.id, load: load, options: options)
        }) { _ in dismiss() }
    }
}

/// P20: fewer minutes today. Optional slots may be removed; required work, warm-up and rest are not.
struct LessTimeSheet: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    @State private var minutes = 35
    var body: some View {
        Group {
            StitchField("Available minutes", value: "\(minutes)") {
                StitchStepperButtons(decrement: { minutes = max(5, minutes - 5) }, increment: { minutes = min(120, minutes + 5) })
            }
            Text("Optional slots can be removed. The fixture will not compress required work, warm-up, or rest.")
                .stitch(.body15).foregroundStyle(Stitch.textSecondary)
            Button("Preview shorter session") { store.request(.shorten(minutes)); dismiss() }.buttonStyle(.stitch())
        }
        .stitchSheet("Less time") { dismiss() }
    }
}

/// P21: move the next session. The sequence does not change and missed work is not added.
struct MoveDaySheet: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    @State private var date = Date().addingTimeInterval(86400)
    var body: some View {
        Group {
            StitchField("Move session to", value: date.formatted(date: .abbreviated, time: .shortened)) {
                DatePicker("Move session to", selection: $date, in: Date()...).labelsHidden()
            }
            Text("This moves the next session only. It does not change the sequence or add missed work.")
                .stitch(.body15).foregroundStyle(Stitch.textSecondary)
            Button("Preview reschedule") { store.request(.reschedule(date)); dismiss() }.buttonStyle(.stitch())
        }
        .stitchSheet("Move day") { dismiss() }
    }
}

/// P22: curated directional alternatives for one slot.
struct SwapSheet: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    let slot: Prescription
    var body: some View {
        Group {
            Text("Alternatives are directional library entries, not a claim of identical loading or safety. The final preview checks your equipment and exclusions.")
                .stitch(.body15).foregroundStyle(Stitch.textSecondary)
            StitchSectionLabel("Instead of \(store.name(slot.exerciseID))", meta: "Today only")
            let alternatives = store.service?.library.exercise(slot.exerciseID)?.alternatives ?? []
            if alternatives.isEmpty {
                StitchNotice("No curated alternative", body: "This exercise has no directional substitute in the library.")
            }
            ForEach(alternatives, id: \.self) { id in
                Button { store.request(.substitute(slot.id, id)); dismiss() } label: {
                    StitchListRow(store.name(id), subtitle: store.service?.library.exercise(id)?.equipmentKind.capitalized ?? "", symbol: "arrow.triangle.swap")
                }
                .buttonStyle(.plain)
            }
        }
        .stitchSheet("Curated swap") { dismiss() }
    }
}

/// Pain sheet (new): pick the exercise; its guidance and any active session pause.
struct PainSheet: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        Group {
            Text("Pick the exercise. Its guidance pauses and your session pauses. A different exercise is not assumed safe — swap it from Today.")
                .stitch(.body15).foregroundStyle(Stitch.textSecondary)
            StitchSectionLabel("Which exercise?", meta: "Today's plan")
            let slots = (store.state.activeSession?.plan ?? store.state.nextPlan)?.slots ?? []
            ForEach(Array(slots.enumerated()), id: \.element.id) { index, slot in
                Button {
                    store.perform({ try $0.reportPain(exerciseID: slot.exerciseID) }) { _ in dismiss() }
                } label: {
                    let role = store.service?.library.exercise(slot.exerciseID)?.role ?? "exercise"
                    StitchListRow(store.name(slot.exerciseID), subtitle: String(format: "Slot %02d · %@", index + 1, role), symbol: "bandage")
                }
                .buttonStyle(.plain)
            }
        }
        .stitchSheet("I'm in pain") { dismiss() }
    }
}

/// A compact line about today's diet that opens the Diet tab. Hidden until diet targets exist.
private struct DietSummaryCard: View {
    @EnvironmentObject private var store: AppStore
    var body: some View {
        if store.diet.status == .ready, let targets = store.diet.targets {
            let left = store.diet.remaining
            Button { store.tab = .diet } label: {
                StitchListRow("Diet today", subtitle: "\(number(left?.calories ?? Double(targets.energyKcal))) kcal · \(number(left?.protein ?? Double(targets.proteinG))) g protein left"
                              + (store.diet.adjustment == nil ? "" : " · suggested change"), symbol: "fork.knife")
            }
            .buttonStyle(.plain)
        }
    }
}


/// ADR-019: an active break, illness or injury, or the way to start one. A status pauses what the app
/// proposes on its own; it never changes the plan and never diagnoses.
struct StatusBanner: View {
    @EnvironmentObject private var store: AppStore
    let onChoose: () -> Void
    var body: some View {
        if let status = store.today.status {
            StitchCard("\(status.kind.label)\(status.endsAt.map { " until \($0.formatted(date: .abbreviated, time: .omitted))" } ?? "")",
                       body: "Automatic suggestions are paused and these days don't count as missed sessions. You can still train and change today's session yourself.",
                       tone: .accent)
            Button("I'm back") { store.perform { try $0.endStatus() } }.buttonStyle(.stitch(.secondary, compact: true))
        } else if store.state.activeSession == nil, store.state.program != nil {
            Button("Taking a break, sick or injured?", action: onChoose).buttonStyle(.stitch(.link))
        }
    }
}

/// Choose the status and how long it lasts; "Until I'm back" leaves the end open.
struct StatusSheet: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    @State private var kind: StatusKind = .onBreak
    @State private var days: Int? = 7
    private let lengths: [(label: String, days: Int?)] = [("3 days", 3), ("1 week", 7), ("2 weeks", 14), ("Until I'm back", nil)]
    var body: some View {
        Group {
            StitchSectionLabel("What's happening")
            HStack(spacing: 8) {
                ForEach(StatusKind.allCases, id: \.self) { option in
                    Button(option.label) { kind = option }.buttonStyle(.stitch(kind == option ? .primary : .secondary, compact: true))
                }
            }
            StitchSectionLabel("For how long")
            ForEach(lengths, id: \.label) { length in
                Button(length.label) { days = length.days }.buttonStyle(.stitch(days == length.days ? .primary : .secondary))
            }
            StitchFootnote("Automatic suggestions pause and these days won't count as missed sessions. Nothing about your plan changes. If you're in pain, use \"I'm in pain\" instead; the app doesn't diagnose.")
            Button("Save") {
                let endsAt = days.map { Date().addingTimeInterval(Double($0) * 86_400) }
                store.perform({ try $0.setStatus(kind, endsAt: endsAt) }) { _ in dismiss() }
            }
            .buttonStyle(.stitch())
        }
        .stitchSheet("Taking a break") { dismiss() }
    }
}
