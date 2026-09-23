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
struct SettingsView: View {
    @EnvironmentObject private var store: AppStore
    @State private var exportDocument = StateExport(data: Data())
    @State private var showExport = false
    @State private var confirmDelete = false
    var body: some View {
        Form {
            Section("Privacy and storage") {
                Label("Stored on this device", systemImage: "lock.shield")
                Text("Workout data is saved atomically with iOS file protection. Cloud sync, accounts, model training, and remote analytics are not enabled.").font(.footnote)
                Toggle("Include in iPhone backups", isOn: Binding(get: { store.includeInDeviceBackup }, set: { store.setIncludeInDeviceBackup($0) }))
                Text(store.includeInDeviceBackup
                     ? "Your training file travels with iCloud Backup and computer backups of this iPhone, encrypted by iOS like the rest of the device. Restoring a backup brings the file back as it was when that backup was made."
                     : "Your training file is left out of iCloud Backup and computer backups. If this iPhone is lost or the app is deleted, the data is gone unless you exported it.").font(.caption)
                Button("Export all local data as JSON") {
                    guard let service = store.service else { return }
                    do { exportDocument = StateExport(data: try service.repository.export()); showExport = true }
                    catch { store.errorMessage = error.localizedDescription }
                }
                Text("Exports contain your training records. Keep copies private. Deleting app data cannot delete files you exported elsewhere.").font(.caption)
            }
            Section("Exercise exclusions") {
                ForEach(store.service?.library.exercises ?? []) { exercise in
                    Toggle(exercise.name, isOn: Binding(get: { store.state.profile?.excludedExercises.contains(exercise.id) ?? false }, set: { value in
                        store.perform { try $0.exclude(exerciseID: exercise.id, excluded: value) }
                    }))
                }
                Text("Enabled toggles mean excluded from guidance, not preferred. Exclusions do not delete historical logs.").font(.caption)
            }
            if !store.state.painExclusions.isEmpty {
                Section("Reported concerns") {
                    ForEach(Array(store.state.painExclusions).sorted(), id: \.self) { Text(store.name($0)) }
                    Text("These persist independently of preferences. A reviewed concern-resolution flow is required before production release; this prototype does not provide medical clearance.").font(.footnote)
                }
            }
            Section("Reference library") {
                NavigationLink("Exercise catalog") { ExerciseCatalogView() }
                NavigationLink("Open-source notices") {
                    ScrollView { Text((try? ThirdPartyNotices.text()) ?? "Notices unavailable").font(.footnote).padding() }
                        .navigationTitle("Open-source notices")
                }
            }
            Section("Build") {
                LabeledContent("Version", value: "0.1.0 development")
                LabeledContent("Local state revision", value: String(store.state.revision))
                LabeledContent("Policy", value: store.service?.library.policy.version ?? "unavailable")
                LabeledContent("Local events", value: String(store.state.events.count))
                Text("P2-P4 are opt-in experiments. Production training content is not approved.")
            }
            Section {
                Button("Delete all local data", role: .destructive) { confirmDelete = true }
            }
        }.navigationTitle("Settings")
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
}


/// Browsing imported descriptions does not enroll an exercise into guidance.
private struct ExerciseCatalogView: View {
    @EnvironmentObject private var store: AppStore
    @State private var catalog: ExerciseCatalog?
    @State private var query = ""
    @State private var error: String?
    private var matches: [CatalogExercise] {
        (catalog?.exercises ?? []).filter { query.isEmpty || $0.name.localizedCaseInsensitiveContains(query) }
    }
    var body: some View {
        List {
            Section {
                Text("Reference descriptions only. These exercises and instructions are not reviewed training guidance and do not change your plan.").font(.footnote)
                if let error { Text(error) }
            }
            ForEach(matches) { exercise in
                NavigationLink(exercise.name) {
                    List {
                        Section("Reference details") {
                            LabeledContent("Equipment", value: exercise.equipment ?? "Not specified")
                            LabeledContent("Muscles", value: exercise.primaryMuscles.joined(separator: ", "))
                            LabeledContent("Level", value: exercise.level)
                        }
                        Section("Upstream instructions — unreviewed") {
                            ForEach(Array(exercise.instructions.enumerated()), id: \.offset) { _, instruction in Text(instruction) }
                        }
                        Section { Text("Source: free-exercise-db · public domain").font(.caption) }
                    }.navigationTitle(exercise.name)
                }
            }
        }.navigationTitle("Exercise catalog")
            .searchable(text: $query)
            .task {
                guard catalog == nil else { return }
                do { catalog = try ExerciseCatalog.bundled() }
                catch { self.error = error.localizedDescription }
            }
    }
}
