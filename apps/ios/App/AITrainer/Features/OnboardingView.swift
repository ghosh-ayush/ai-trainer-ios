import SwiftUI
import AITrainerCore

struct OnboardingView: View {
    @EnvironmentObject private var store: AppStore
    @State private var profile = Profile()
    @State private var acknowledgesFixture = false
    @State private var preview: Program?
    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("Build a training history.\nMake the next session count.")
                        .font(.largeTitle.bold()).padding(.vertical)
                    PhaseNotice(title: "P1 development preview", detail: "This build uses sample programs and test policies. They are not approved training prescriptions. No camera, wearable, or account is needed.")
                }
                Section("Scope") {
                    Toggle("I am 18 or older", isOn: $profile.adultConfirmed)
                    Toggle("I am exploring general resistance training, not clinical or rehabilitation programming", isOn: $profile.supportedScopeConfirmed)
                    Toggle("I understand the program is a development fixture", isOn: $acknowledgesFixture)
                }
                Section("Your preferences") {
                    Picker("Primary goal", selection: $profile.goal) {
                        Text("Hypertrophy").tag("Hypertrophy"); Text("Strength").tag("Strength")
                    }
                    Picker("Experience", selection: $profile.experience) {
                        Text("Beginner").tag("Beginner"); Text("Intermediate").tag("Intermediate")
                    }
                    Stepper("\(profile.daysPerWeek) available days per week", value: $profile.daysPerWeek, in: 2...4)
                    Stepper("\(profile.minutes) minutes per session", value: $profile.minutes, in: 20...90, step: 5)
                    Picker("Preferred unit", selection: $profile.preferredUnit) {
                        ForEach(MassUnit.allCases) { Text($0.rawValue).tag($0) }
                    }
                }
                Section("Available equipment") {
                    equipmentToggle("Dumbbells", id: "dumbbell")
                    equipmentToggle("Barbell and rack", id: "barbell")
                    equipmentToggle("Machines and cables", id: "machine")
                }
                Section {
                    Button("Preview sample program") {
                        guard let service = store.service else { return }
                        do { preview = try service.previewInitialPlan(profile: profile, now: Date()) }
                        catch { store.errorMessage = error.localizedDescription }
                    }
                    .disabled(!profile.adultConfirmed || !profile.supportedScopeConfirmed || !acknowledgesFixture || !AppStore.isDevelopment)
                    if !AppStore.isDevelopment {
                        Text("Release builds cannot activate fixture content. A reviewed content bundle is required.").foregroundStyle(.secondary)
                    }
                } footer: {
                    Text("No date of birth, sex, body weight, or estimated strength is required. Your data stays on this device.")
                }
            }
            .navigationTitle("AI Trainer").navigationBarTitleDisplayMode(.inline)
            .sheet(item: $preview) { program in
                NavigationStack {
                    List {
                        Section("Review before accepting") {
                            Text("One repeating full-body session. This is not yet a reviewed multi-day split.")
                            ForEach(program.plans.flatMap(\.slots)) { slot in
                                VStack(alignment: .leading) {
                                    Text(store.name(slot.exerciseID)).font(.headline)
                                    Text("Fixture: \(slot.workingSets) sets, \(slot.lowerReps)-\(slot.upperReps) reps. Working load remains unknown.").font(.subheadline)
                                }
                            }
                        }
                        Button("Accept sample plan") {
                            if store.perform({ try $0.acceptInitialPlan(profile: profile) }) { preview = nil }
                        }.buttonStyle(.borderedProminent)
                    }.navigationTitle("Program preview")
                        .toolbar { Button("Cancel") { preview = nil } }
                }
            }
        }
    }
    private func equipmentToggle(_ label: String, id: String) -> some View {
        Toggle(label, isOn: Binding(get: { profile.equipment.contains(id) }, set: { value in
            if value { profile.equipment.insert(id) } else { profile.equipment.remove(id) }
        }))
    }
}
