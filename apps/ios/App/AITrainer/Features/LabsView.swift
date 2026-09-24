import SwiftUI
import AITrainerCore

/// P25 Developer ▸ Labs (was the Labs tab; Debug builds only). Experiments never write training evidence.
struct LabsView: View {
    @EnvironmentObject private var store: AppStore
    var body: some View {
        DetailScreen("Developer") {
            StitchNotice("Separate experiments, shared boundaries",
                         body: "These tools do not write camera or recovery estimates into P1 progression. Enable them explicitly for development testing.")
            StitchToggleField("Enable experimental tools", isOn: $store.experimentalToolsEnabled)
                .disabled(!AppStore.isDevelopment)
            if AppStore.isDevelopment && store.experimentalToolsEnabled {
                StitchSectionLabel("P0 - feasibility")
                link("Camera / device benchmark", subtitle: "P0 benchmark", symbol: "speedometer") { CameraLabView(benchmarkOnly: true) }
                StitchSectionLabel("P2 - camera pilot")
                link("Right-arm curl counter experiment", subtitle: "Unvalidated 2D angle thresholds. No form grading, joint-force estimates, or real-time safety cues.", symbol: "camera") {
                    CameraLabView(benchmarkOnly: false)
                }
                StitchSectionLabel("P3 - recovery integration")
                link("Read Apple Health signals", subtitle: "Raw readings only. Personal-baseline and adaptation policies are not approved.", symbol: "heart.text.square") { RecoveryView() }
                StitchSectionLabel("P4 - nutrition pilot")
                link("Meals and reusable portions", subtitle: "User-confirmed estimates. No food-photo recognition or volumetric reconstruction.", symbol: "fork.knife") { NutritionView() }
            }
            StitchSectionLabel("Research only")
            Text("Inverse dynamics, lumbar loading, injury prediction, and calibrated food geometry have no execution path into released guidance.")
                .stitch(.body15).foregroundStyle(Stitch.textSecondary)
        }
    }
    private func link<Destination: View>(_ title: String, subtitle: String, symbol: String, @ViewBuilder destination: () -> Destination) -> some View {
        NavigationLink(destination: destination) { StitchListRow(title, subtitle: subtitle, symbol: symbol) }.buttonStyle(.plain)
    }
}

/// P26 / P27 / P54: camera benchmark and the curl-counter pilot. Counts are never saved as sets.
struct CameraLabView: View {
    let benchmarkOnly: Bool
    @StateObject private var camera = CameraService()
    @Environment(\.scenePhase) private var scenePhase
    var body: some View {
        DetailScreen(benchmarkOnly ? "P0 benchmark" : "P2 camera pilot") {
            CameraPreview(session: camera.session).frame(height: 330)
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).strokeBorder(Stitch.glassStroke))
            Text(camera.message).stitch(.body13).foregroundStyle(Stitch.textSecondary)
            HStack(spacing: 8) {
                Button(camera.running ? "Stop camera" : "Start local camera") {
                    if camera.running { camera.stop() } else { camera.start() }
                }
                .buttonStyle(.stitch())
                Button("Reset count") { camera.resetCount() }.buttonStyle(.stitch(.secondary))
            }
            if !benchmarkOnly {
                StitchCard {
                    StitchStat("Experimental reps", value: "\(camera.observation.count)", unit: "reps")
                    Text(camera.observation.status).stitch(.bodyMedium13).foregroundStyle(Stitch.textPrimary)
                    StitchKeyValue("2D elbow angle", value: "\(camera.observation.angle.map(number) ?? "unassessed") °")
                    StitchKeyValue("Last cycle", value: "\(camera.observation.lastDuration.map(number) ?? "unassessed") s")
                    StitchKeyValue("Tracking dropouts", value: "\(camera.observation.dropouts)")
                    StitchFootnote("Keep one person in view. This right-arm curl experiment uses fixture thresholds and is not an accuracy or safety assessment. Counts are not saved as workout sets.")
                }
            }
            StitchSectionLabel("Measured on this device")
            StitchCard {
                StitchKeyValue("Processed frames", value: String(camera.frameCount))
                StitchKeyValue("Processed frames / second", value: number(camera.processedFPS))
                StitchKeyValue("Pipeline p50 / p95", value: "\(number(camera.p50)) / \(number(camera.p95)) ms")
                StitchKeyValue("Vision request revision", value: String(camera.modelRevision))
                TimelineView(.periodic(from: .now, by: 2)) { _ in
                    StitchKeyValue("Thermal · battery", value: "\(thermalLabel) · \(batteryLabel)")
                }
                StitchFootnote("Latency percentiles cover the latest 300 processed frames, including failed detections. They are diagnostic measurements, not validation results.")
            }
            StitchFootnote("No video is recorded or uploaded. Test camera position, lighting, occlusion, and sustained thermal behavior on real devices.")
        }
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

/// P28 / P29 / P61: read-only Apple Health samples. No readiness score; nothing modifies training.
struct RecoveryView: View {
    @EnvironmentObject private var store: AppStore
    @StateObject private var health = HealthKitService()
    var body: some View {
        DetailScreen("Recovery signals") {
            StitchCard("P3 read-only integration",
                       body: "Read HRV (SDNN), resting heart rate, and sleep samples from Apple Health. This screen does not diagnose fatigue, combine duplicate sleep sources, calculate readiness, or modify training.")
            Button(health.loading ? "Reading..." : "Request access & read samples") {
                guard let core = store.service?.core else { return }
                Task { await health.requestAndRead(using: core) }
            }
            .buttonStyle(.stitch()).disabled(health.loading || store.service == nil)
            if health.loading { ProgressView().tint(Stitch.accentPrimary).frame(maxWidth: .infinity) }
            StitchFootnote(health.message)
            ForEach(health.readings) { reading in
                StitchCard {
                    StitchKeyValue(reading.title, value: reading.value)
                    Text("\(reading.source) · \(reading.date.formatted(date: .abbreviated, time: .shortened))").stitch(.body13).foregroundStyle(Stitch.textMuted)
                }
            }
            StitchFootnote("At most 300 samples per type; HRV/RHR window 28 days, sleep 7 days. Records stay in this screen's memory. No baseline is fabricated from missing data.")
            Button("Clear local display") { health.clear() }.buttonStyle(.stitch(.secondary))
        }
        .onDisappear { health.clear() }
    }
}
