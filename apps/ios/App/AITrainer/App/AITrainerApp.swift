import SwiftUI
import UIKit
import AITrainerCore

@main
@MainActor
struct AITrainerApp: App {
    @StateObject private var store = AppStore()
    init() {
        Stitch.registerFonts()
        StitchChrome.configure()
        #if DEBUG
        if ProcessInfo.processInfo.arguments.contains("--core-smoke-test") { CoreSmokeTest.run() }
        #endif
    }
    var body: some Scene {
        WindowGroup { RootView().environmentObject(store) }
    }
}

/// UIKit appearance for the system bars so the tab bar and pushed navigation bars match the Stitch kit.
enum StitchChrome {
    static func configure() {
        let chrome = UIColor(red: 16 / 255, green: 20 / 255, blue: 26 / 255, alpha: 0.78)
        let muted = UIColor(red: 144 / 255, green: 143 / 255, blue: 160 / 255, alpha: 1)
        let accent = UIColor(red: 192 / 255, green: 193 / 255, blue: 255 / 255, alpha: 1)
        let primary = UIColor(red: 223 / 255, green: 226 / 255, blue: 235 / 255, alpha: 1)
        let hairline = UIColor(red: 38 / 255, green: 42 / 255, blue: 49 / 255, alpha: 1)

        let tabs = UITabBarAppearance()
        tabs.configureWithTransparentBackground()
        tabs.backgroundEffect = UIBlurEffect(style: .systemUltraThinMaterialDark)
        tabs.backgroundColor = chrome
        tabs.shadowColor = hairline
        let tabFont = UIFont(name: "JetBrainsMono-Medium", size: 11) ?? .monospacedSystemFont(ofSize: 11, weight: .medium)
        for layout in [tabs.stackedLayoutAppearance, tabs.inlineLayoutAppearance, tabs.compactInlineLayoutAppearance] {
            layout.normal.iconColor = muted
            layout.normal.titleTextAttributes = [.font: tabFont, .foregroundColor: muted, .kern: 0.275]
            layout.selected.iconColor = accent
            layout.selected.titleTextAttributes = [.font: tabFont, .foregroundColor: accent, .kern: 0.275]
        }
        UITabBar.appearance().standardAppearance = tabs
        UITabBar.appearance().scrollEdgeAppearance = tabs

        let bar = UINavigationBarAppearance()
        bar.configureWithTransparentBackground()
        bar.backgroundEffect = UIBlurEffect(style: .systemUltraThinMaterialDark)
        bar.backgroundColor = chrome
        bar.shadowColor = hairline
        bar.titleTextAttributes = [.foregroundColor: primary, .font: UIFont(name: "SpaceGrotesk-Bold", size: 20) ?? .boldSystemFont(ofSize: 20)]
        bar.largeTitleTextAttributes = [.foregroundColor: primary, .font: UIFont(name: "SpaceGrotesk-Bold", size: 28) ?? .boldSystemFont(ofSize: 28)]
        let back = UIBarButtonItemAppearance()
        back.normal.titleTextAttributes = [.foregroundColor: accent, .font: UIFont(name: "Inter-Medium", size: 15) ?? .systemFont(ofSize: 15)]
        bar.backButtonAppearance = back
        UINavigationBar.appearance().standardAppearance = bar
        UINavigationBar.appearance().scrollEdgeAppearance = bar
        UINavigationBar.appearance().compactAppearance = bar
        UINavigationBar.appearance().tintColor = accent
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
/// `TrainerService`, then publishes state snapshots and the core's view models to the views.
@MainActor
final class AppStore: ObservableObject {
    @Published private(set) var state = AthleteState()
    /// Today's slot cards and proposal titles, recomputed by the core after every change.
    @Published private(set) var today = TodayStatus()
    /// Recorded values per exercise for the Progress tab.
    @Published private(set) var progress: [ExerciseProgress] = []
    /// The Diet tab: targets, what is left today, the weight trend, a suggested adjustment and food ideas.
    @Published private(set) var diet = DietView()
    /// The selected tab, so a card on one tab can open another.
    @Published var tab: AppTab = .today
    /// The session just finished, shown as a summary card on Today until the next start.
    @Published var justFinishedSessionID: UUID?
    @Published var errorMessage: String?
    @Published var experimentalToolsEnabled = false
    @Published var showPreviewInfo = false
    /// True while a change runs on the core queue; further taps are ignored until it lands.
    @Published private(set) var isWorking = false
    /// Whether the state file participates in iCloud/computer backups of this device (B.1).
    @Published private(set) var includeInDeviceBackup: Bool
    let service: TrainerService?
    let startupFailure: StartupFailure?
    private let persistence: FilePersistence?
    private static let includeInDeviceBackupKey = "includeInDeviceBackup"
    /// Every core call made on behalf of the UI runs here, one at a time, off the main thread.
    private let coreQueue = DispatchQueue(label: "ai.trainer.core", qos: .userInitiated)
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
        // Loading the bundled content doubles as the probe that the embedded core runs at all.
        let library: ContentLibrary
        do { library = try core.library(permitsFixtures: Self.isDevelopment) } catch {
            service = nil; persistence = nil; startupFailure = .runtime(error.localizedDescription)
            return
        }
        do {
            let root = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
            let filePersistence = try FilePersistence(url: root.appendingPathComponent("AITrainer/state.json"),
                                                      excludedFromBackup: !includeInBackup)
            let repository = try StateRepository(persistence: filePersistence, core: core)
            service = TrainerService(repository: repository, library: library, core: core)
            persistence = filePersistence
            startupFailure = nil
            state = repository.snapshot
            perform { _ in }  // computes Today and Progress off the main thread
        } catch {
            service = nil; persistence = nil; startupFailure = .savedData(error.localizedDescription)
        }
    }
    /// Runs `action` on the core queue, then refreshes Today and Progress there too, and publishes
    /// the result on the main actor. A failure shows the alert; `then` runs only after success.
    /// Taps that arrive while a change is still in flight are ignored, so a button that has not yet
    /// updated cannot submit the same thing twice.
    func perform<Value>(_ action: @escaping (TrainerService) throws -> Value, then: @escaping (Value) -> Void = { _ in }) {
        guard let service, !isWorking else { return }
        isWorking = true
        let job = CoreJob(value: (service: service, action: action, then: then))
        coreQueue.async {
            let outcome = Result { try job.value.action(job.value.service) }
            let delivery = CoreJob(value: (outcome: outcome, refreshed: Self.refreshed(job.value.service)))
            Task { @MainActor in
                let (outcome, refreshed) = delivery.value
                self.state = refreshed.state
                if let views = refreshed.views { self.today = views.today; self.progress = views.progress; self.diet = views.diet }
                self.isWorking = false
                switch outcome {
                case .success(let value):
                    job.value.then(value)
                    if let error = refreshed.error { self.errorMessage = error.localizedDescription }
                case .failure(let error):
                    self.errorMessage = error.localizedDescription
                }
            }
        }
    }
    /// Runs a read-only core call (food search, diet preview) on the core queue without the refresh
    /// and tap-gating of `perform`; `then` receives the answer on the main actor, errors show the alert.
    func read<Value>(_ query: @escaping (TrainerService) throws -> Value, then: @escaping (Value) -> Void) {
        guard let service else { return }
        let job = CoreJob(value: (service: service, query: query, then: then))
        coreQueue.async {
            let outcome = CoreJob(value: Result { try job.value.query(job.value.service) })
            Task { @MainActor in
                switch outcome.value {
                case .success(let value): job.value.then(value)
                case .failure(let error): self.errorMessage = error.localizedDescription
                }
            }
        }
    }
    /// Asks for a change the athlete chose (less time, move day, swap). A non-proposal answer is shown.
    func request(_ request: TrainingRequest) {
        perform({ try $0.request(request) }) { decision in
            if decision.outcome != .proposeChange { self.errorMessage = decision.explanation }
        }
    }
    /// Today and Progress from the core, computed on the core queue. When the core names a slot to
    /// auto-request, its progression proposal is requested once — so proposals appear without a review step.
    nonisolated private static func refreshed(_ service: TrainerService) -> (state: AthleteState, views: CoreViews?, error: Error?) {
        guard service.repository.snapshot.profile != nil else { return (service.repository.snapshot, nil, nil) }
        do {
            var views = try service.views()
            if let slotID = views.today.autoRequest {
                try service.request(.progression(slotID))
                views = try service.views()
            }
            return (service.repository.snapshot, views, nil)
        } catch {
            return (service.repository.snapshot, nil, error)
        }
    }
    func name(_ id: String) -> String { service?.library.exercise(id)?.name ?? id }
    /// True when the bundled content passed the automated evidence gate (ADR-014), not a fixture.
    var contentIsApproved: Bool { service?.library.policy.review == .approved }
    /// Whether a plan can be activated in this build: approved content always, fixtures only in Debug.
    var canActivatePlan: Bool {
        guard let library = service?.library else { return false }
        return library.policy.review == .approved || (library.policy.review == .fixture && library.permitsFixtures)
    }
    /// The header pill: "PREVIEW FIXTURE · fixture-1" for test content, "EVIDENCE-BASED · <version>" for
    /// approved content (it must say so — ADR-006), nothing when content is disabled.
    var previewPill: String? {
        guard let library = service?.library else { return nil }
        if library.policy.review == .approved { return "Evidence-based · \(library.policy.version)" }
        guard library.permitsFixtures, library.policy.review == .fixture else { return nil }
        return "Preview fixture · \(library.policy.version)"
    }
    var previewPillTone: StitchPill.Tone { contentIsApproved ? .lavender : .amber }
    /// Flips the backup attribute on the state directory first; the preference is only recorded
    /// once the file system accepted the change, so the toggle never lies about what is backed up.
    func setIncludeInDeviceBackup(_ include: Bool) {
        do { try persistence?.setExcludedFromBackup(!include) }
        catch { errorMessage = error.localizedDescription; return }
        includeInDeviceBackup = include
        UserDefaults.standard.set(include, forKey: Self.includeInDeviceBackupKey)
    }
}

/// Carries a core call and its result between the main actor and the core queue. Unchecked because
/// the queue is serial and `TrainerService` keeps all mutable state behind `StateRepository`'s lock
/// and the transport's interpreter lock; closures from views only read values they captured.
private struct CoreJob<Wrapped>: @unchecked Sendable { let value: Wrapped }

enum AppTab: Hashable { case today, diet, progress, you }

struct RootView: View {
    @EnvironmentObject private var store: AppStore
    var body: some View {
        Group {
            if case .runtime(let error) = store.startupFailure {
                StartupGateView(title: "Training engine did not start", symbol: "cpu", detail: error,
                    advice: "This build's bundled training rules could not run, so the app read nothing and changed nothing. Your saved data is untouched. Update the app, or report this build.")
            } else if case .savedData(let error) = store.startupFailure {
                StartupGateView(title: "Saved data needs attention", symbol: "externaldrive.badge.exclamationmark", detail: error,
                    advice: "Your file was not reset. Unlock the device and reopen the app; preserve its container before recovery.")
            } else if store.state.profile == nil {
                OnboardingView()
            } else {
                TabView(selection: $store.tab) {
                    NavigationStack { TodayView() }
                        .tabItem { Label("TODAY", systemImage: "sun.max") }.tag(AppTab.today)
                    NavigationStack { DietTabView() }
                        .tabItem { Label("DIET", systemImage: "fork.knife") }.tag(AppTab.diet)
                    NavigationStack { ProgressTabView() }
                        .tabItem { Label("PROGRESS", systemImage: "chart.xyaxis.line") }.tag(AppTab.progress)
                    NavigationStack { YouView() }
                        .tabItem { Label("YOU", systemImage: "gearshape") }.tag(AppTab.you)
                }
            }
        }
        .tint(Stitch.accentPrimary)
        .preferredColorScheme(.dark)
        .sheet(isPresented: $store.showPreviewInfo) { PreviewInfoSheet() }
        .alert("Trainer update", isPresented: Binding(get: { store.errorMessage != nil }, set: { if !$0 { store.errorMessage = nil } })) {
            Button("OK", role: .cancel) { store.errorMessage = nil }
        } message: { Text(store.errorMessage ?? "") }
    }
}

/// P56 / P37: the two launch gates. Nothing was read or written when either is shown.
private struct StartupGateView: View {
    let title: String
    let symbol: String
    let detail: String
    let advice: String
    var body: some View {
        VStack(spacing: 0) {
            StitchRootHeader("AI Trainer", pill: nil)
            Group {
                Image(systemName: symbol).font(.system(size: 40)).foregroundStyle(Stitch.accentPrimary)
                    .frame(maxWidth: .infinity).padding(.top, 24)
                Text(title).stitch(.displayH2).foregroundStyle(Stitch.textPrimary).frame(maxWidth: .infinity)
                StitchNotice(title, body: detail, tone: .danger)
                Text(advice).stitch(.body15).foregroundStyle(Stitch.textSecondary)
            }
            .stitchScrollColumn()
        }
        .background { StitchBackdrop() }
    }
}

/// PInfo: replaces every inline "phase" notice. Opened from the preview pill in any header.
struct PreviewInfoSheet: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        Group {
            let version = store.service?.library.policy.version ?? "unknown"
            if store.contentIsApproved {
                StitchNotice("Evidence-based content · \(version)",
                             body: "Sets, reps, rest and progression rules come from published research, cited in the content manifest. They were not reviewed by a clinician or coach.")
            } else {
                StitchNotice("Development preview · policy \(version)",
                             body: "Sample programs and test policies. They are not approved training prescriptions. Release builds refuse this content.",
                             tone: .warn)
            }
            Text("What the app never does: estimate your strength, fill unknown effort, change your plan without your acceptance, or let camera, sleep or meals write training evidence. No account, no network, no language model in the decision path.")
                .stitch(.body15).foregroundStyle(Stitch.textSecondary)
            Button("Got it") { dismiss() }.buttonStyle(.stitch())
        }
        .stitchSheet(store.contentIsApproved ? "About this content" : "Preview build") { dismiss() }
    }
}

/// A tab root: the Stitch root header pinned above a scrolling column, system bar hidden.
struct TabRoot<Content: View>: View {
    @EnvironmentObject private var store: AppStore
    let title: String
    let content: Content
    init(_ title: String, @ViewBuilder content: () -> Content) { self.title = title; self.content = content() }
    var body: some View {
        content
            .stitchScrollColumn()
            .safeAreaInset(edge: .top, spacing: 0) {
                StitchRootHeader(title, pill: store.previewPill, pillTone: store.previewPillTone) { store.showPreviewInfo = true }
            }
            .toolbar(.hidden, for: .navigationBar)
    }
}

/// A pushed screen: system bar with the Stitch appearance, inline title and the preview pill.
struct DetailScreen<Content: View>: View {
    @EnvironmentObject private var store: AppStore
    let title: String
    let content: Content
    init(_ title: String, @ViewBuilder content: () -> Content) { self.title = title; self.content = content() }
    var body: some View {
        content
            .stitchScrollColumn()
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if let pill = store.previewPill {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button { store.showPreviewInfo = true } label: { StitchPill(pill.components(separatedBy: " · ").first ?? pill, tone: store.previewPillTone) }
                            .buttonStyle(.plain)
                    }
                }
            }
    }
}

func number(_ value: Double) -> String { value.formatted(.number.precision(.fractionLength(0...2))) }
func parseOptionalNumber(_ text: String) throws -> Double? {
    let clean = text.trimmingCharacters(in: .whitespacesAndNewlines)
    if clean.isEmpty { return nil }
    guard let value = Double(clean), value.isFinite, value >= 0 else { throw TrainerError.invalid("Enter a nonnegative number, or leave unknown values blank.") }
    return value
}

#if DEBUG
/// Simulator/device diagnostic uses memory only, never the user's saved athlete state.
private enum CoreSmokeTest {
    static func run() {
        var result: [String: Any] = [:]
        do {
            let core = LocalPythonTrainerService(transport: EmbeddedPythonTransport())
            let repository = try StateRepository(persistence: MemoryPersistence(), core: core)
            let service = TrainerService(repository: repository, library: try core.library(permitsFixtures: true), core: core)
            var profile = Profile(); profile.adultConfirmed = true; profile.supportedScopeConfirmed = true
            profile.equipment = ["barbell", "dumbbell", "machine"]; profile.preferredExercises = ["bench"]
            let now = Date(timeIntervalSince1970: 1_789_689_600)
            try service.acceptInitialPlan(profile: profile, now: now)
            guard let slot = repository.snapshot.nextPlan?.slots.first else { throw TrainerError.notFound }
            try service.configureLoad(slotID: slot.id, load: 100, options: [100, 105])
            for days in [5.0, 2.0] {
                let date = now.addingTimeInterval(-days * 86400)
                try service.start(now: date)
                guard let session = repository.snapshot.activeSession else { throw TrainerError.notFound }
                for index in 0..<3 {
                    try service.saveSet(sessionID: session.id, slotID: slot.id, index: index, load: 100, reps: 10, rir: 2, now: date)
                }
                try service.finish(now: date.addingTimeInterval(1800))
            }
            let decision = try service.request(.progression(slot.id), now: now)
            guard decision.reason == "QUALIFYING_EXPOSURES_COMPLETE",
                  let rec = repository.snapshot.recommendations.last else { throw TrainerError.invalid("Progression smoke failed: " + decision.reason) }
            try service.acceptRecommendation(id: rec.id, now: now)
            guard repository.snapshot.nextPlan?.slots.first?.load == 105 else { throw TrainerError.invalid("Acceptance smoke failed") }
            guard try service.views(now: now).progress.first?.entries.count == 2 else { throw TrainerError.invalid("Progress smoke failed") }
            let nutrients = try service.scaleNutrients(Nutrients(calories: 200, protein: 10), servings: 2)
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
