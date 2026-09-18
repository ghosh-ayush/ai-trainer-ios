import SwiftUI
import AITrainerCore

@main
@MainActor
struct AITrainerApp: App {
    @StateObject private var store = AppStore()
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
