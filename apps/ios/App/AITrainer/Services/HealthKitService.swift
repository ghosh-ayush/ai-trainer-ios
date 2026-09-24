import Foundation
import Combine
import HealthKit
import AITrainerCore

struct HealthReading: Identifiable, Codable {
    let id: UUID
    let title: String
    let value: String
    let date: Date
    let source: String
}
@MainActor
final class HealthKitService: ObservableObject {
    @Published private(set) var readings: [HealthReading] = []
    @Published private(set) var message = "Not connected"
    @Published private(set) var loading = false
    private let healthStore = HKHealthStore()
    private var generation = 0
    /// Reads samples and asks the domain core to classify them. The core always answers
    /// `unassessed` today (no reviewed readiness policy); anything else is treated as an error.
    func requestAndRead(using core: LocalPythonTrainerService) async {
        guard !loading else { return }
        guard HKHealthStore.isHealthDataAvailable() else { message = "HealthKit is not available on this device."; return }
        guard let hrv = HKObjectType.quantityType(forIdentifier: .heartRateVariabilitySDNN),
              let rhr = HKObjectType.quantityType(forIdentifier: .restingHeartRate),
              let sleep = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else { return }
        loading = true; generation += 1; let requestGeneration = generation
        defer { loading = false }
        readings = []
        do {
            // Completion does NOT prove that read access was granted.
            try await healthStore.requestAuthorization(toShare: [], read: Set<HKObjectType>([hrv, rhr, sleep]))
            let start = Date().addingTimeInterval(-28 * 86400)
            let hrvSamples = try await samples(type: hrv, since: start)
            let rhrSamples = try await samples(type: rhr, since: start)
            let sleepSamples = try await samples(type: sleep, since: Date().addingTimeInterval(-7 * 86400))
            var result: [HealthReading] = []
            for sample in hrvSamples.compactMap({ $0 as? HKQuantitySample }) {
                result.append(HealthReading(id: sample.uuid, title: "HRV (SDNN)", value: "\(number(sample.quantity.doubleValue(for: .secondUnit(with: .milli)))) ms", date: sample.startDate, source: sample.sourceRevision.source.name))
            }
            for sample in rhrSamples.compactMap({ $0 as? HKQuantitySample }) {
                result.append(HealthReading(id: sample.uuid, title: "Resting heart rate", value: "\(number(sample.quantity.doubleValue(for: HKUnit.count().unitDivided(by: .minute())))) bpm", date: sample.startDate, source: sample.sourceRevision.source.name))
            }
            for sample in sleepSamples.compactMap({ $0 as? HKCategorySample }) {
                let label: String
                switch sample.value {
                case HKCategoryValueSleepAnalysis.asleepCore.rawValue: label = "Core sleep sample"
                case HKCategoryValueSleepAnalysis.asleepDeep.rawValue: label = "Deep sleep sample"
                case HKCategoryValueSleepAnalysis.asleepREM.rawValue: label = "REM sleep sample"
                case HKCategoryValueSleepAnalysis.asleepUnspecified.rawValue: label = "Sleep sample (unspecified)"
                default: continue
                }
                result.append(HealthReading(id: sample.uuid, title: label, value: "\(number(sample.endDate.timeIntervalSince(sample.startDate) / 60)) minutes", date: sample.startDate, source: sample.sourceRevision.source.name))
            }
            guard requestGeneration == generation else { return }
            struct Payload: Encodable { let observations: [HealthReading] }
            struct Assessment: Decodable { let status: String; let reason: String }
            let assessment: Assessment = try core.call("recovery", Payload(observations: result))
            guard assessment.status == "unassessed" else { throw TrainerError.unsupported }
            readings = result.sorted { $0.date > $1.date }
            message = result.isEmpty ? "No readable samples. Data may be absent, outside the shared window, or not permitted." : "Read-only samples; no readiness score or training adjustment."
        } catch { message = error.localizedDescription }
    }
    private func samples(type: HKSampleType, since: Date) async throws -> [HKSample] {
        try await withCheckedThrowingContinuation { continuation in
            let predicate = HKQuery.predicateForSamples(withStart: since, end: Date(), options: .strictStartDate)
            let query = HKSampleQuery(sampleType: type, predicate: predicate, limit: 300, sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]) { _, samples, error in
                if let error { continuation.resume(throwing: error) }
                else { continuation.resume(returning: samples ?? []) }
            }
            healthStore.execute(query)
        }
    }
    func clear() { generation += 1; readings = []; message = "Local display cleared. Manage Health permissions in iOS Settings." }

    /// Body-mass samples from the last `days` days as weigh-ins for the diet engine (ADR-016).
    /// Read-only: nothing is written to Health. An empty answer can also mean read access was
    /// not granted — HealthKit does not say which — so the caller must not treat it as "no change".
    func bodyMassWeighIns(days: Int = 90) async throws -> [WeighIn] {
        guard HKHealthStore.isHealthDataAvailable() else { throw TrainerError.invalid("Apple Health is not available on this device.") }
        guard let bodyMass = HKObjectType.quantityType(forIdentifier: .bodyMass) else { return [] }
        loading = true
        defer { loading = false }
        try await healthStore.requestAuthorization(toShare: [], read: [bodyMass])
        let since = Date().addingTimeInterval(-Double(days) * 86400)
        return try await samples(type: bodyMass, since: since).compactMap { $0 as? HKQuantitySample }.map { sample in
            WeighIn(id: UUID(), kg: sample.quantity.doubleValue(for: .gramUnit(with: .kilo)), measuredAt: sample.startDate,
                    source: "appleHealth", timeZone: TimeZone.current.identifier,
                    utcOffsetSeconds: TimeZone.current.secondsFromGMT(for: sample.startDate))
        }
    }
}
