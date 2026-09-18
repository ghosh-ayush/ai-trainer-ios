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

@MainActor
final class AppStore: ObservableObject {
    @Published private(set) var state = AthleteState()
    @Published var errorMessage: String?
    @Published var experimentalToolsEnabled = false
    let service: TrainerService?
    let startupError: String?
    static var isDevelopment: Bool {
        #if DEBUG
        return true
        #else
        return false
        #endif
    }
    init() {
        do {
            _ = try LocalPythonTrainerService.shared.call("nutrients", RuntimeProbeNutrients(), as: Nutrients.self)
            let root = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
            let persistence = try FilePersistence(url: root.appendingPathComponent("AITrainer/state.json"))
            let repository = try StateRepository(persistence: persistence)
            service = TrainerService(repository: repository, library: ContentLibrary(permitsFixtures: Self.isDevelopment))
            state = repository.snapshot; startupError = nil
        } catch { service = nil; startupError = error.localizedDescription }
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
    func name(_ id: String) -> String { service?.brain.library.exercise(id)?.name ?? id }
}

struct RootView: View {
    @EnvironmentObject private var store: AppStore
    var body: some View {
        Group {
            if let error = store.startupError {
                ContentUnavailableView("Saved data needs attention", systemImage: "externaldrive.badge.exclamationmark", description: Text(error + " Your file was not reset. Unlock the device and reopen the app; preserve its container before recovery."))
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
            let repository = try StateRepository(persistence: MemoryPersistence())
            let service = TrainerService(repository: repository, library: ContentLibrary(permitsFixtures: true))
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
            let nutrients = try Nutrients(calories: 200, protein: 10).scaled(by: 2)
            let catalog = try ExerciseCatalog.bundled()
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
