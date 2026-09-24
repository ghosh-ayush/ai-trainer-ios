import SwiftUI
import UniformTypeIdentifiers
import AITrainerCore

struct StateExport: FileDocument {
    static var readableContentTypes: [UTType] { [.json] }
    var data: Data
    init(data: Data) { self.data = data }
    init(configuration: ReadConfiguration) throws { data = configuration.file.regularFileContents ?? Data() }
    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper { FileWrapper(regularFileWithContents: data) }
}

/// P35 You (was Settings): profile, data & privacy, exercises I avoid, reference, developer, delete.
struct YouView: View {
    @EnvironmentObject private var store: AppStore
    @State private var exportDocument = StateExport(data: Data())
    @State private var showExport = false
    @State private var confirmDelete = false
    var body: some View {
        TabRoot("You") {
            if let profile = store.state.profile {
                StitchSectionLabel("Profile", meta: "Read-only until TB-10")
                StitchCard("\(profile.goal) · \(profile.experience) · \(profile.daysPerWeek) days/week",
                           body: "\(profile.minutes) min sessions · \(profile.preferredUnit.rawValue) · \(equipmentText(profile)). Editing arrives with program review (TB-10).")
            }
            StitchSectionLabel("Data & privacy")
            StitchCard {
                Label("Stored on this device", systemImage: "lock.shield").stitch(.displayH3).foregroundStyle(Stitch.textPrimary)
                Text("Workout data is saved atomically with iOS file protection. Cloud sync, accounts, model training, and remote analytics are not enabled.")
                    .stitch(.body13).foregroundStyle(Stitch.textSecondary)
            }
            StitchToggleField("Include in iPhone backups", isOn: Binding(get: { store.includeInDeviceBackup }, set: { store.setIncludeInDeviceBackup($0) }))
            StitchFootnote(store.includeInDeviceBackup
                ? "Your training file travels with iCloud Backup and computer backups of this iPhone, encrypted by iOS like the rest of the device. Restoring a backup brings the file back as it was when that backup was made."
                : "Your training file is left out of iCloud Backup and computer backups. If this iPhone is lost or the app is deleted, the data is gone unless you exported it.")
            Button("Export all local data as JSON") {
                guard let service = store.service else { return }
                do { exportDocument = StateExport(data: try service.repository.export()); showExport = true }
                catch { store.errorMessage = error.localizedDescription }
            }
            .buttonStyle(.stitch(.secondary))
            StitchFootnote("Exports contain your training records. Keep copies private. Deleting app data cannot delete files you exported elsewhere.")

            StitchSectionLabel("Exercises I avoid", meta: "Exclusions + reported concerns")
            ForEach(store.service?.library.exercises ?? []) { exercise in
                if store.state.painExclusions.contains(exercise.id) {
                    StitchField(exercise.name, value: "Reported concern · paused") {
                        Image(systemName: "bandage.fill").foregroundStyle(Stitch.dangerPrimary)
                    }
                } else {
                    StitchToggleField(exercise.name, isOn: Binding(
                        get: { store.state.profile?.excludedExercises.contains(exercise.id) ?? false },
                        set: { value in store.perform { try $0.exclude(exerciseID: exercise.id, excluded: value) } }),
                        on: "Excluded", off: "Not excluded")
                }
            }
            StitchFootnote("Enabled toggles mean excluded from guidance, not preferred. Exclusions do not delete historical logs. Reported concerns stay until a reviewed resolution flow exists; this app does not provide medical clearance.")

            StitchSectionLabel("Reference")
            NavigationLink { ExerciseCatalogView() } label: {
                StitchListRow("Exercise catalog", subtitle: "876 reference descriptions", symbol: "books.vertical")
            }
            .buttonStyle(.plain)
            NavigationLink { NoticesView() } label: {
                StitchListRow("Open-source notices", subtitle: "Third-party licenses", symbol: "doc.text")
            }
            .buttonStyle(.plain)

            if AppStore.isDevelopment {
                StitchCard {
                    StitchSectionLabel("Developer", meta: "Debug builds only")
                    NavigationLink { LabsView() } label: {
                        StitchListRow("Labs — experiments", subtitle: "Camera benchmark · curl counter · Apple Health · meals", symbol: "flask")
                    }
                    .buttonStyle(.plain)
                    StitchKeyValue("Version", value: "0.1.0 development")
                    StitchKeyValue("Local state revision", value: String(store.state.revision))
                    StitchKeyValue("Policy", value: store.service?.library.policy.version ?? "unavailable")
                    StitchKeyValue("Local events", value: String(store.state.events.count))
                    StitchFootnote("Labs never write training evidence. Hidden in Release builds.")
                }
            }
            Button("Delete all local data", role: .destructive) { confirmDelete = true }.buttonStyle(.stitch(.destructive))
        }
        .fileExporter(isPresented: $showExport, document: exportDocument, contentType: .json, defaultFilename: "AITrainer-private-export") { result in
            if case .failure(let error) = result { store.errorMessage = error.localizedDescription }
        }
        .confirmationDialog("Delete all local records, preferences, meals, and audit history?", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("Delete everything on this device", role: .destructive) {
                store.perform { try $0.repository.deleteAll() }
                store.experimentalToolsEnabled = false
            }
        }
    }
    private func equipmentText(_ profile: Profile) -> String {
        let names = ["dumbbell": "Dumbbells", "barbell": "Barbell", "machine": "Machines"]
        return profile.equipment.sorted().map { names[$0] ?? $0.capitalized }.joined(separator: ", ")
    }
}

/// P53 Open-source notices.
private struct NoticesView: View {
    var body: some View {
        DetailScreen("Open-source notices") {
            Text((try? ThirdPartyNotices.text()) ?? "Notices unavailable").stitch(.monoSmall).foregroundStyle(Stitch.textSecondary)
                .textSelection(.enabled)
        }
    }
}

/// P50 / P51 / P52: browsing imported descriptions never enrols an exercise into guidance.
private struct ExerciseCatalogView: View {
    @EnvironmentObject private var store: AppStore
    @State private var catalog: ExerciseCatalog?
    @State private var query = ""
    @State private var error: String?
    private var matches: [CatalogExercise] {
        (catalog?.exercises ?? []).filter { query.isEmpty || $0.name.localizedCaseInsensitiveContains(query) }
    }
    var body: some View {
        DetailScreen("Exercise catalog") {
            StitchNotice("Reference descriptions only", body: "These exercises and instructions are not reviewed training guidance and do not change your plan.")
            if let error { StitchNotice("Catalog unavailable", body: error, tone: .danger) }
            if catalog != nil, matches.isEmpty {
                StitchCard("No results", body: "No reference description matches “\(query)”.")
            }
            LazyVStack(spacing: 8) {
                ForEach(matches) { exercise in
                    NavigationLink { CatalogDetailView(exercise: exercise) } label: {
                        StitchListRow(exercise.name, subtitle: [exercise.equipment, exercise.level].compactMap { $0 }.joined(separator: " · "), symbol: "text.book.closed")
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .searchable(text: $query)
        .task {
            guard catalog == nil else { return }
            do { catalog = try ExerciseCatalog.bundled() }
            catch { self.error = error.localizedDescription }
        }
    }
}

private struct CatalogDetailView: View {
    let exercise: CatalogExercise
    var body: some View {
        DetailScreen(exercise.name) {
            StitchSectionLabel("Reference details")
            StitchCard {
                StitchKeyValue("Equipment", value: exercise.equipment ?? "Not specified")
                StitchKeyValue("Muscles", value: exercise.primaryMuscles.joined(separator: ", "))
                StitchKeyValue("Level", value: exercise.level)
            }
            StitchSectionLabel("Upstream instructions", meta: "Unreviewed")
            ForEach(Array(exercise.instructions.enumerated()), id: \.offset) { index, instruction in
                HStack(alignment: .top, spacing: 10) {
                    Text("\(index + 1)").stitch(.monoBodyBold).foregroundStyle(Stitch.accentPrimary)
                    Text(instruction).stitch(.body15).foregroundStyle(Stitch.textSecondary)
                }
            }
            if let evidence = exercise.evidence, !evidence.isEmpty {
                StitchSectionLabel("What research found", meta: "\(evidence.count) cited")
                StitchNotice("Reference only", body: "These study findings describe the exercise. They do not change your plan.")
                ForEach(Array(evidence.enumerated()), id: \.offset) { _, entry in
                    CatalogEvidenceCard(entry: entry)
                }
            }
            StitchFootnote("Source: free-exercise-db · public domain")
        }
    }
}

/// One cited finding for a catalog exercise, shown with its certainty and source.
private struct CatalogEvidenceCard: View {
    let entry: CatalogEvidence
    var body: some View {
        StitchCard {
            StitchKeyValue(Self.outcomeLabel(entry.outcome), value: Self.resultLabel(entry.result, outcome: entry.outcome))
            StitchKeyValue("Muscles", value: entry.muscles.isEmpty ? "Whole body" : entry.muscles.joined(separator: ", "))
            Text(entry.finding).stitch(.body15).foregroundStyle(Stitch.textSecondary)
            StitchKeyValue("Certainty", value: entry.certainty + (entry.fullTextRead ? "" : " · abstract only"))
            Text("\(entry.citation) \(entry.locator).").stitch(.monoSmall).foregroundStyle(Stitch.textSecondary)
                .textSelection(.enabled)
        }
    }

    static func outcomeLabel(_ outcome: String) -> String {
        switch outcome {
        case "muscleActivation": return "Activation (EMG)"
        case "hypertrophy": return "Muscle growth"
        case "strength": return "Strength"
        case "localEndurance": return "Muscular endurance"
        case "power": return "Power"
        case "agility": return "Agility"
        case "posture": return "Posture"
        case "cardiorespiratory": return "Stamina"
        default: return outcome
        }
    }

    /// EMG compares activation only, so its results never read as "better" or "worse" training.
    static func resultLabel(_ result: String, outcome: String) -> String {
        let activation = outcome == "muscleActivation"
        switch result {
        case "favoured": return activation ? "Higher activation" : "Did better"
        case "lessFavoured": return activation ? "Lower activation" : "Did worse"
        case "noDifference": return "No clear difference"
        default: return "Studied"
        }
    }
}
