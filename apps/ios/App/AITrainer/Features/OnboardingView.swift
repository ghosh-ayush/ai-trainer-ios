import SwiftUI
import AITrainerCore

/// P01 Onboarding: one consent toggle, preferences, equipment, then the program preview (P02).
/// Minutes and unit use defaults here and can be changed later. P40: Release builds block the CTA.
struct OnboardingView: View {
    @EnvironmentObject private var store: AppStore
    @State private var profile = OnboardingView.defaultProfile
    @State private var consent = false
    @State private var preview: Program?
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
                StitchField("Consent", value: "I'm 18+, exploring general resistance training (not clinical or rehab), and I understand this is a development preview") {
                    Toggle("Consent", isOn: $consent).labelsHidden().tint(Stitch.accentPrimary)
                }
                StitchSectionLabel("Your preferences", meta: "\(profile.minutes) min · \(profile.preferredUnit.rawValue) by default")
                selection("Primary goal", value: $profile.goal, options: ["Hypertrophy", "Strength"])
                selection("Experience", value: $profile.experience, options: ["Beginner", "Intermediate"])
                StitchField("Available days per week", value: "\(profile.daysPerWeek)") {
                    StitchStepperButtons(decrement: { profile.daysPerWeek = max(2, profile.daysPerWeek - 1) },
                                         increment: { profile.daysPerWeek = min(4, profile.daysPerWeek + 1) })
                }
                StitchSectionLabel("Available equipment")
                equipmentToggle("Dumbbells", id: "dumbbell")
                equipmentToggle("Barbell and rack", id: "barbell")
                equipmentToggle("Machines and cables", id: "machine")
                if AppStore.isDevelopment {
                    Button("Preview sample program") { previewProgram() }.buttonStyle(.stitch()).disabled(!consent)
                } else {
                    Button("Preview sample program") {}.buttonStyle(.stitch()).disabled(true)
                    StitchNotice("Release build", body: "Release builds cannot activate fixture content. A reviewed content bundle is required.", tone: .warn)
                }
                StitchFootnote("No date of birth, sex, body weight or estimated strength. Minutes and unit can be changed later. Your data stays on this device.")
            }
        }
        .sheet(item: $preview) { ProgramPreviewSheet(program: $0, profile: acceptedProfile) { preview = nil } }
    }
    /// The single consent toggle covers the adult and scope confirmations the core requires.
    private var acceptedProfile: Profile {
        var accepted = profile
        accepted.adultConfirmed = consent
        accepted.supportedScopeConfirmed = consent
        return accepted
    }
    private func previewProgram() {
        guard let service = store.service else { return }
        do { preview = try service.previewInitialPlan(profile: acceptedProfile) }
        catch { store.errorMessage = error.localizedDescription }
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

/// P02 Program preview: what accepting creates. Working loads stay unknown until you confirm them.
private struct ProgramPreviewSheet: View {
    @EnvironmentObject private var store: AppStore
    let program: Program
    let profile: Profile
    let onClose: () -> Void
    var body: some View {
        Group {
            StitchSectionLabel("Review before accepting", meta: program.templateID)
            StitchNotice("One repeating full-body session", body: "This is not yet a reviewed multi-day split.")
            ForEach(program.plans.flatMap(\.slots)) { slot in
                StitchCard(store.name(slot.exerciseID) + (slot.optional ? " · optional" : ""),
                           body: "Fixture: \(slot.workingSets) sets, \(slot.lowerReps)-\(slot.upperReps) reps. Working load remains unknown.")
            }
            Button("Accept sample plan") {
                if store.perform({ try $0.acceptInitialPlan(profile: profile) }) { onClose() }
            }
            .buttonStyle(.stitch())
        }
        .stitchSheet("Program preview", onCancel: onClose)
    }
}
