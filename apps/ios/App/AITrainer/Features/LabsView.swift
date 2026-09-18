import SwiftUI
import AITrainerCore

struct LabsView: View {
    @EnvironmentObject private var store: AppStore
    var body: some View {
        List {
            Section {
                PhaseNotice(title: "Separate experiments, shared boundaries", detail: "These tools do not write camera or recovery estimates into P1 progression. Enable them explicitly for development testing.")
                Toggle("Enable experimental tools", isOn: $store.experimentalToolsEnabled).disabled(!AppStore.isDevelopment)
            }
            if AppStore.isDevelopment && store.experimentalToolsEnabled {
                Section("P0 - feasibility") {
                    NavigationLink { CameraLabView(benchmarkOnly: true) } label: { Label("Camera / device benchmark", systemImage: "speedometer") }
                }
                Section("P2 - camera pilot") {
                    NavigationLink { CameraLabView(benchmarkOnly: false) } label: { Label("Right-arm curl counter experiment", systemImage: "camera") }
                    Text("Unvalidated 2D angle thresholds. No form grading, joint-force estimates, or real-time safety cues.").font(.caption)
                }
                Section("P3 - recovery integration") {
                    NavigationLink { RecoveryView() } label: { Label("Read Apple Health signals", systemImage: "heart.text.square") }
                    Text("Raw readings only. Personal-baseline and adaptation policies are not approved.").font(.caption)
                }
                Section("P4 - nutrition pilot") {
                    NavigationLink { NutritionView() } label: { Label("Meals and reusable portions", systemImage: "fork.knife") }
                    Text("User-confirmed estimates. No food-photo recognition or volumetric reconstruction.").font(.caption)
                }
            }
            Section("Research only") {
                Text("Inverse dynamics, lumbar loading, injury prediction, and calibrated food geometry have no execution path into released guidance.")
            }
        }.navigationTitle("Phase labs")
    }
}
struct CameraLabView: View {
    let benchmarkOnly: Bool
    @StateObject private var camera = CameraService()
    @Environment(\.scenePhase) private var scenePhase
    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                CameraPreview(session: camera.session).frame(height: 330).clipShape(RoundedRectangle(cornerRadius: 20))
                Text(camera.message).font(.subheadline)
                HStack {
                    Button(camera.running ? "Stop camera" : "Start local camera") {
                        if camera.running { camera.stop() } else { camera.start() }
                    }.buttonStyle(.borderedProminent)
                    Button("Reset count") { camera.resetCount() }.buttonStyle(.bordered)
                }
                if !benchmarkOnly {
                    Panel {
                        Text("\(camera.observation.count) experimental reps").font(.largeTitle.bold())
                        Text(camera.observation.status)
                        Text("2D elbow angle: \(camera.observation.angle.map(number) ?? "unassessed") degrees")
                        Text("Last cycle: \(camera.observation.lastDuration.map(number) ?? "unassessed") seconds")
                        Text("Tracking dropouts: \(camera.observation.dropouts)")
                        Text("Keep one person in view. This right-arm curl experiment uses fixture thresholds and is not an accuracy or safety assessment. Counts are not saved as workout sets.").font(.footnote).foregroundStyle(.secondary)
                    }
                }
                Panel {
                    Text("Measured on this device").font(.headline)
                    LabeledContent("Processed frames", value: String(camera.frameCount))
                    LabeledContent("Processed frames / second", value: number(camera.processedFPS))
                    LabeledContent("Pipeline p50 / p95", value: "\(number(camera.p50)) / \(number(camera.p95)) ms")
                    LabeledContent("Vision request revision", value: String(camera.modelRevision))
                    Text("Latency percentiles cover the latest 300 processed frames, including failed detections. They are diagnostic measurements, not validation results.").font(.caption)
                    TimelineView(.periodic(from: .now, by: 2)) { _ in
                        Text("Thermal state: \(thermalLabel) · Battery: \(batteryLabel)").font(.caption)
                    }
                }
                Text("No video is recorded or uploaded. Test camera position, lighting, occlusion, and sustained thermal behavior on real devices.").font(.footnote)
            }.padding()
        }.background(Color(uiColor: .systemGroupedBackground))
            .navigationTitle(benchmarkOnly ? "P0 benchmark" : "P2 camera pilot")
            .onAppear { UIDevice.current.isBatteryMonitoringEnabled = true }
            .onDisappear { camera.stop(); UIDevice.current.isBatteryMonitoringEnabled = false }
            .onChange(of: scenePhase) { _, phase in if phase != .active { camera.stop() } }
    }
    private var batteryLabel: String {
        let level = UIDevice.current.batteryLevel
        return level < 0 ? "unavailable" : "\(Int(level * 100))%"
    }
    private var thermalLabel: String {
        switch ProcessInfo.processInfo.thermalState {
        case .nominal: return "nominal"
        case .fair: return "fair"
        case .serious: return "serious"
        case .critical: return "critical"
        @unknown default: return "unknown"
        }
    }
}
struct RecoveryView: View {
    @StateObject private var health = HealthKitService()
    var body: some View {
        List {
            Section {
                Text("P3 read-only integration").font(.headline)
                Text("Read HRV (SDNN), resting heart rate, and sleep samples from Apple Health. This screen does not diagnose fatigue, combine duplicate sleep sources, calculate readiness, or modify training.")
                Button(health.loading ? "Reading..." : "Request access & read samples") { Task { await health.requestAndRead() } }.disabled(health.loading)
                Text(health.message).font(.footnote)
            }
            ForEach(health.readings) { reading in
                VStack(alignment: .leading, spacing: 4) {
                    HStack { Text(reading.title).font(.headline); Spacer(); Text(reading.value) }
                    Text("\(reading.source) · \(reading.date.formatted(date: .abbreviated, time: .shortened))").font(.caption).foregroundStyle(.secondary)
                }
            }
            Section {
                Text("At most 300 samples per type; HRV/RHR window 28 days, sleep 7 days. Records stay in this screen's memory. No baseline is fabricated from missing data.").font(.caption)
                Button("Clear local display") { health.clear() }
            }
        }.navigationTitle("Recovery signals").onDisappear { health.clear() }
    }
}
