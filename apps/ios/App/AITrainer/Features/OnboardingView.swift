import SwiftUI
import AITrainerCore

/// P01 Onboarding: one consent toggle, preferences, free weekdays and minutes, equipment, then the
/// week options (ADR-017) and the program preview (P02). No free day is preselected: the athlete
/// picks them. P40: Release builds block the CTA.
struct OnboardingView: View {
    @EnvironmentObject private var store: AppStore
    @State private var profile = OnboardingView.defaultProfile
    @State private var consent = false
    @State private var preview: Program?
    @State private var weekChoice: WeekChoice?
    private static var defaultProfile: Profile {
        var profile = Profile()
        profile.minutes = 45
        profile.preferredUnit = .kg
        return profile
    }
    var body: some View {
        NavigationStack {
            TabRoot("Onboarding") {
                Text("Build a training history.\nMake the next session count.").stitch(.displayH2).foregroundStyle(Stitch.textPrimary)
                StitchSectionLabel("Consent", meta: "1 required")
                StitchField("Consent", value: consentText) {
                    Toggle("Consent", isOn: $consent).labelsHidden().tint(Stitch.accentPrimary)
                }
                StitchSectionLabel("Your preferences", meta: "\(profile.minutes) min · \(profile.preferredUnit.rawValue) by default")
                selection("Primary goal", value: $profile.goal, options: ["Hypertrophy", "Strength"])
                selection("Experience", value: $profile.experience, options: ["Beginner", "Intermediate"])
                StitchSectionLabel("Free days", meta: freeDaysMeta)
                WeekdayPicker(freeDays: Binding(get: { profile.freeDays ?? [] }, set: { setFreeDays($0) }))
                StitchField("Minutes per session", value: "\(profile.minutes) min") {
                    StitchStepperButtons(decrement: { profile.minutes = max(15, profile.minutes - 5) },
                                         increment: { profile.minutes = min(120, profile.minutes + 5) })
                }
                StitchSectionLabel("Available equipment")
                equipmentToggle("Dumbbells", id: "dumbbell")
                equipmentToggle("Barbell and rack", id: "barbell")
                equipmentToggle("Machines and cables", id: "machine")
                Button(store.contentIsApproved ? "See my week options" : "Preview sample program") { previewProgram() }
                    .buttonStyle(.stitch()).disabled(!consent || !store.canActivatePlan || (profile.freeDays ?? []).isEmpty)
                if !store.canActivatePlan {
                    StitchNotice("Release build", body: "Release builds cannot activate fixture content. A reviewed content bundle is required.", tone: .warn)
                }
                StitchFootnote("No date of birth, sex, body weight or estimated strength. Minutes and unit can be changed later. Your data stays on this device.")
            }
        }
        .sheet(item: $preview) { ProgramPreviewSheet(program: $0, profile: acceptedProfile, optionID: nil) { preview = nil } }
        .sheet(item: $weekChoice) { WeekChoiceSheet(options: $0.options, profile: acceptedProfile) { weekChoice = nil } }
    }
    private var freeDaysMeta: String {
        let count = profile.freeDays?.count ?? 0
        return count == 0 ? "tap the days you can train" : "\(count) day\(count == 1 ? "" : "s") a week"
    }
    /// The athlete's free weekdays; the number of days follows them, so the core never guesses which days.
    private func setFreeDays(_ days: [Int]) {
        profile.freeDays = days.isEmpty ? nil : days
        profile.daysPerWeek = max(1, days.count)
    }
    private var consentText: String {
        let scope = "I'm 18+, exploring general resistance training (not clinical or rehab)"
        return store.contentIsApproved
            ? scope + ", and I understand the guidance is evidence-based, not clinician-reviewed"
            : scope + ", and I understand this is a development preview"
    }
    /// The single consent toggle covers the adult and scope confirmations the core requires.
    private var acceptedProfile: Profile {
        var accepted = profile
        accepted.adultConfirmed = consent
        accepted.supportedScopeConfirmed = consent
        return accepted
    }
    /// Weekly content (ADR-017) offers distinct weeks to choose from; one-session content previews directly.
    private func previewProgram() {
        let athlete = acceptedProfile
        store.perform({ service -> (options: [WeekOption], single: Program?) in
            let options = try service.weekOptions(profile: athlete)
            return (options, options.isEmpty ? try service.previewInitialPlan(profile: athlete) : nil)
        }) { result in
            if let single = result.single {
                preview = single
            } else {
                weekChoice = WeekChoice(options: result.options)
            }
        }
    }
    private func selection(_ label: String, value: Binding<String>, options: [String]) -> some View {
        Menu {
            Picker(label, selection: value) { ForEach(options, id: \.self) { Text($0).tag($0) } }
        } label: {
            StitchField(label, value: value.wrappedValue) { Image(systemName: "chevron.right").foregroundStyle(Stitch.textMuted) }
        }
    }
    private func equipmentToggle(_ label: String, id: String) -> some View {
        StitchToggleField(label, isOn: Binding(get: { profile.equipment.contains(id) }, set: { value in
            if value { profile.equipment.insert(id) } else { profile.equipment.remove(id) }
        }), on: "Available", off: "Unavailable")
    }
}

/// The options the core returned, as one sheet item.
private struct WeekChoice: Identifiable {
    let id = UUID()
    let options: [WeekOption]
}

/// ADR-017: up to three genuinely different weeks for the athlete's free days, best first, each with
/// the reasons the core gives. Choosing one shows its program; nothing changes until Accept.
private struct WeekChoiceSheet: View {
    @EnvironmentObject private var store: AppStore
    let options: [WeekOption]
    let profile: Profile
    let onClose: () -> Void
    @State private var chosen: (optionID: String, program: Program)?
    var body: some View {
        Group {
            if let chosen {
                ProgramPreviewContent(program: chosen.program, profile: profile, optionID: chosen.optionID, onClose: onClose)
                Button("Back to the options") { self.chosen = nil }.buttonStyle(.stitch(.link))
            } else {
                StitchSectionLabel("Choose your week", meta: "\(options.count) option\(options.count == 1 ? "" : "s")")
                ForEach(Array(options.enumerated()), id: \.element.id) { index, option in
                    StitchCard(tone: index == 0 ? .accent : .default) {
                        Text("\(option.name) · \(option.sessionsPerWeek) day\(option.sessionsPerWeek == 1 ? "" : "s")")
                            .stitch(.displayH3).foregroundStyle(Stitch.textPrimary)
                        Text(WeekOptionText.schedule(option)).stitch(.body13).foregroundStyle(Stitch.textSecondary)
                        ForEach(option.reasons, id: \.self) { reason in
                            Text("• " + WeekOptionText.explanation(reason)).stitch(.body13).foregroundStyle(Stitch.textSecondary)
                        }
                        Button(index == 0 ? "Preview the suggested week" : "Preview this week") { preview(option) }
                            .buttonStyle(.stitch(index == 0 ? .primary : .secondary))
                    }
                }
                StitchFootnote("Every option keeps the research limits: weekly sets per muscle, sets per session and rest between sessions for the same muscle. Reduced weeks fit your time with fewer sets than the weekly target.")
            }
        }
        .stitchSheet("Your week", onCancel: onClose)
    }
    private func preview(_ option: WeekOption) {
        store.perform({ try $0.previewInitialPlan(profile: profile, optionID: option.id) }) { program in
            chosen = (option.id, program)
        }
    }
}

/// How a week option reads: its schedule and the core's reason codes in plain words (ADR-017).
enum WeekOptionText {
    static func schedule(_ option: WeekOption) -> String {
        let days = option.sessions.map { "\(Weekday.short($0.weekday)) \($0.name) \(Int($0.minutes.rounded())) min" }
        return days.joined(separator: " · ") + " — about \(Int(option.weeklyMinutes.rounded())) min a week"
    }
    /// Plain words for the core's reason codes.
    static func explanation(_ reason: String) -> String {
        switch reason {
        case "REACHES_WEEKLY_FLOOR": return "Reaches the weekly set target for every major muscle"
        case "REDUCED_VOLUME_FOR_TIME": return "Fewer sets than the weekly target, to fit your time; the key lifts stay"
        case "EACH_MUSCLE_TWICE_OR_MORE": return "Each major muscle trained at least twice a week"
        case "NO_MUSCLE_ON_BACK_TO_BACK_DAYS": return "No muscle trained on back-to-back days"
        case "SPREAD_ACROSS_THE_WEEK": return "Sessions spread evenly across the week"
        case "FITS_RECENT_ROUTINE": return "Fits how often you have been training"
        case "A_SPLIT_YOU_LIKE": return "A split you said you like"
        default: return reason
        }
    }
}

/// P02 Program preview: what accepting creates. Working loads stay unknown until you confirm them.
private struct ProgramPreviewSheet: View {
    let program: Program
    let profile: Profile
    let optionID: String?
    let onClose: () -> Void
    var body: some View {
        Group { ProgramPreviewContent(program: program, profile: profile, optionID: optionID, onClose: onClose) }
            .stitchSheet("Program preview", onCancel: onClose)
    }
}

/// The plans a program holds, one section per session (with its weekday for a weekly plan).
private struct ProgramPreviewContent: View {
    @EnvironmentObject private var store: AppStore
    let program: Program
    let profile: Profile
    let optionID: String?
    let onClose: () -> Void
    var body: some View {
        StitchSectionLabel("Review before accepting", meta: "\(program.plans.count) session\(program.plans.count == 1 ? "" : "s") a week")
        if program.plans.count == 1, program.plans.first?.weekday == nil {
            StitchNotice("One repeating full-body session", body: "This content has no weekly planner yet.")
        }
        ForEach(program.plans) { plan in
            StitchSectionLabel(plan.weekday.map { "\(Weekday.name($0)) · \(plan.name)" } ?? plan.name,
                               meta: "about \(plan.estimatedMinutes) min")
            ForEach(plan.slots) { slot in
                StitchCard(store.name(slot.exerciseID) + (slot.optional ? " · optional" : ""),
                           body: "\(store.contentIsApproved ? "" : "Fixture: ")\(slot.workingSets) sets, \(slot.lowerReps)-\(slot.upperReps) reps. Working load remains unknown.")
            }
        }
        Button(store.contentIsApproved ? "Accept plan" : "Accept sample plan") {
            store.perform({ try $0.acceptInitialPlan(profile: profile, optionID: optionID) }) { _ in onClose() }
        }
        .buttonStyle(.stitch())
    }
}
