import SwiftUI
import AITrainerCore

@main
@MainActor
struct AITrainerApp: App {
    @StateObject private var store = AppStore()
    init() {
        #if DEBUG
        if ProcessInfo.processInfo.arguments.contains("--core-smoke-test") { CoreSmokeTest.run() }
        #endif
    }
    var body: some Scene {
        WindowGroup { RootView().environmentObject(store) }
    }
}

/// Why the app could not reach a usable `TrainerService` at launch. The two cases need different
/// advice: a runtime failure is a broken build, a saved-data failure is the user's file.
enum StartupFailure {
    /// The embedded Python core did not answer a trivial request. Nothing was read or written.
    case runtime(String)
    /// The core works but the saved state file could not be read. The file was not touched.
    case savedData(String)
}

/// The app's composition root: builds the one domain core, the one repository and the one
/// `TrainerService`, then publishes state snapshots to the views.
@MainActor
final class AppStore: ObservableObject {
    @Published private(set) var state = AthleteState()
    @Published var errorMessage: String?
    @Published var experimentalToolsEnabled = false
    /// Whether the state file participates in iCloud/computer backups of this device (B.1).
    @Published private(set) var includeInDeviceBackup: Bool
    let service: TrainerService?
    let startupFailure: StartupFailure?
    private let persistence: FilePersistence?
    private static let includeInDeviceBackupKey = "includeInDeviceBackup"
    static var isDevelopment: Bool {
        #if DEBUG
        return true
        #else
        return false
        #endif
    }
    init() {
        let defaults = UserDefaults.standard
        let includeInBackup = defaults.object(forKey: Self.includeInDeviceBackupKey) as? Bool ?? true
        includeInDeviceBackup = includeInBackup
        let core = LocalPythonTrainerService(transport: EmbeddedPythonTransport())
        do {
            _ = try core.call("nutrients", RuntimeProbeNutrients(), as: Nutrients.self)
        } catch {
            service = nil; persistence = nil; startupFailure = .runtime(error.localizedDescription)
            return
        }
        do {
            let root = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
            let filePersistence = try FilePersistence(url: root.appendingPathComponent("AITrainer/state.json"),
                                                      excludedFromBackup: !includeInBackup)
            let repository = try StateRepository(persistence: filePersistence)
            service = TrainerService(repository: repository, library: ContentLibrary(permitsFixtures: Self.isDevelopment), core: core)
            persistence = filePersistence
            startupFailure = nil
            state = repository.snapshot
        } catch {
            service = nil; persistence = nil; startupFailure = .savedData(error.localizedDescription)
        }
    }
    @discardableResult func perform(_ action: (TrainerService) throws -> Void) -> Bool {
        guard let service else { return false }
        do { try action(service); state = service.repository.snapshot; return true }
        catch { errorMessage = error.localizedDescription; state = service.repository.snapshot; return false }
    }
    func request(_ request: Request) {
        perform { service in
            let result = try service.request(request)
            if result.outcome != .proposeChange { errorMessage = result.explanation }
        }
    }
    func name(_ id: String) -> String { service?.library.exercise(id)?.name ?? id }
    /// Flips the backup attribute on the state directory first; the preference is only recorded
    /// once the file system accepted the change, so the toggle never lies about what is backed up.
    func setIncludeInDeviceBackup(_ include: Bool) {
        do { try persistence?.setExcludedFromBackup(!include) }
        catch { errorMessage = error.localizedDescription; return }
        includeInDeviceBackup = include
        UserDefaults.standard.set(include, forKey: Self.includeInDeviceBackupKey)
    }
}

struct RootView: View {
    @EnvironmentObject private var store: AppStore
    var body: some View {
        Group {
            if case .runtime(let error) = store.startupFailure {
                ContentUnavailableView("Training engine did not start", systemImage: "cpu",
                    description: Text(error + " This build's bundled training rules could not run, so the app read nothing and changed nothing. Your saved data is untouched. Update the app, or report this build."))
            } else if case .savedData(let error) = store.startupFailure {
                ContentUnavailableView("Saved data needs attention", systemImage: "externaldrive.badge.exclamationmark",
                    description: Text(error + " Your file was not reset. Unlock the device and reopen the app; preserve its container before recovery."))
            } else if store.state.profile == nil {
                OnboardingView()
            } else {
                TabView {
                    NavigationStack { TodayView() }.tabItem { Label("Today", systemImage: "sun.max") }
                    NavigationStack { HistoryView() }.tabItem { Label("History", systemImage: "chart.xyaxis.line") }
                    NavigationStack { CoachView() }.tabItem { Label("Coach", systemImage: "bubble.left.and.text.bubble.right") }
                    NavigationStack { LabsView() }.tabItem { Label("Labs", systemImage: "flask") }
                    NavigationStack { SettingsView() }.tabItem { Label("Settings", systemImage: "gearshape") }
                }
            }
        }
        .tint(.indigo)
        .alert("Trainer update", isPresented: Binding(get: { store.errorMessage != nil }, set: { if !$0 { store.errorMessage = nil } })) {
            Button("OK", role: .cancel) { store.errorMessage = nil }
        } message: { Text(store.errorMessage ?? "") }
    }
}

struct Panel<Content: View>: View {
    private let content: Content
    init(@ViewBuilder content: () -> Content) { self.content = content() }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) { content }
            .frame(maxWidth: .infinity, alignment: .leading).padding(18)
            .background(.background, in: RoundedRectangle(cornerRadius: 20))
    }
}
struct PhaseNotice: View {
    let title: String
    let detail: String
    var body: some View {
        Label { VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.subheadline.bold())
            Text(detail).font(.footnote).foregroundStyle(.secondary)
        } } icon: { Image(systemName: "info.circle") }
    }
}
func number(_ value: Double) -> String { value.formatted(.number.precision(.fractionLength(0...2))) }
func parseOptionalNumber(_ text: String) throws -> Double? {
    let clean = text.trimmingCharacters(in: .whitespacesAndNewlines)
    if clean.isEmpty { return nil }
    guard let value = Double(clean), value.isFinite, value >= 0 else { throw TrainerError.invalid("Enter a nonnegative number, or leave unknown values blank.") }
    return value
}

private struct RuntimeProbeNutrients: Encodable {
    let nutrients = Nutrients(); let servings = 1.0
}
#if DEBUG
/// Simulator/device diagnostic uses memory only, never the user's saved athlete state.
private enum CoreSmokeTest {
    static func run() {
        var result: [String: Any] = [:]
        do {
            let core = LocalPythonTrainerService(transport: EmbeddedPythonTransport())
            let repository = try StateRepository(persistence: MemoryPersistence())
            let service = TrainerService(repository: repository, library: ContentLibrary(permitsFixtures: true), core: core)
            var profile = Profile(); profile.adultConfirmed = true; profile.supportedScopeConfirmed = true
            profile.equipment = ["barbell", "dumbbell", "machine"]; profile.preferredExercises = ["bench"]
            let now = Date(timeIntervalSince1970: 1_789_689_600)
            try service.acceptInitialPlan(profile: profile, now: now)
            guard let slot = repository.snapshot.nextPlan?.slots.first else { throw TrainerError.notFound }
            try service.configureLoad(slotID: slot.id, load: 100, options: [100, 105])
            for days in [5.0, 2.0] {
                let date = now.addingTimeInterval(-days * 86400)
                try service.start(now: date)
                guard let session = repository.snapshot.activeSession,
                      let prescription = session.plan.slots.first else { throw TrainerError.notFound }
                for index in 0..<3 {
                    try service.saveSet(SetLog(prescription: prescription, index: index, load: 100, reps: 10, rir: 2, occurredAt: date), sessionID: session.id)
                }
                try service.finish(now: date.addingTimeInterval(1800))
            }
            let decision = try service.request(.progression(slot.id), now: now)
            guard decision.reason == "QUALIFYING_EXPOSURES_COMPLETE",
                  let rec = repository.snapshot.recommendations.last else { throw TrainerError.invalid("Progression smoke failed: " + decision.reason) }
            try service.acceptRecommendation(id: rec.id, now: now)
            guard repository.snapshot.nextPlan?.slots.first?.load == 105 else { throw TrainerError.invalid("Acceptance smoke failed") }
            let nutrients = try service.scaleNutrients(Nutrients(calories: 200, protein: 10), servings: 2)
            let catalog = try ExerciseCatalog.bundled(core: core)
            guard nutrients.calories == 400, catalog.exercises.count == 876 else { throw TrainerError.invalid("Content smoke failed") }
            result = ["passed": true, "runtime": "embedded CPython", "catalogCount": catalog.exercises.count,
                      "decision": decision.reason, "appliedLoad": 105, "networkRequired": false]
        } catch { result = ["passed": false, "error": String(describing: error)] }
        if let url = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first?.appendingPathComponent("core-smoke-result.json"),
           let data = try? JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys]) {
            try? data.write(to: url, options: .atomic)
        }
        print("AI_TRAINER_CORE_SMOKE", result)
    }
}
#endif
