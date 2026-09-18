import Foundation
import RepCounterSDK
import Vision
import CoreVideo

public struct PosePoint: Equatable {
    public var x: Double
    public var y: Double
    public var confidence: Double
    public init(x: Double, y: Double, confidence: Double) { self.x = x; self.y = y; self.confidence = confidence }
}
public struct RepObservation: Equatable {
    public var count = 0
    public var lastDuration: Double?
    public var angle: Double?
    public var status = "Unassessed"
    public var dropouts = 0
    public init() {}
}
/// Experimental right-arm adapter. SDK owns geometry and hysteresis; this wrapper
/// rejects unreliable input and retains the fixture's debounce/duration boundaries.
/// All access must be serialized (CameraService uses its capture queue).
public final class CurlCounter {
    private let detector = RepDetector(spec: .reps(name: "AI Trainer right-arm fixture", enter: 1, exit: 0) { pose in
        pose.elbowAngle(.right).map { max(0, min(1, (150 - $0) / 85)) }
    })
    private var stableExtended = 0
    private var stableFlexed = 0
    private var hasBaseline = false
    private var started: TimeInterval?
    private var lastTimestamp: TimeInterval?
    public private(set) var observation = RepObservation()
    public init() {}
    public func reset() {
        detector.reset(); stableExtended = 0; stableFlexed = 0; hasBaseline = false
        started = nil; lastTimestamp = nil; observation = RepObservation()
    }
    public func consume(shoulder: PosePoint?, elbow: PosePoint?, wrist: PosePoint?, timestamp: TimeInterval) -> RepObservation {
        guard timestamp.isFinite else { return observation }
        if let last = lastTimestamp, timestamp <= last { return observation }
        if let last = lastTimestamp, timestamp - last > 0.5 { invalidate() }
        lastTimestamp = timestamp
        guard let a = shoulder, let b = elbow, let c = wrist,
              [a, b, c].allSatisfy({ $0.confidence >= 0.5 && $0.x.isFinite && $0.y.isFinite }),
              let angle = Self.angle(a, b, c) else {
            invalidate(); observation.status = "Unassessed - reposition phone"; return observation
        }
        observation.angle = angle; observation.status = "Experimental observation (RepCounterSDK)"
        if angle < 150, hasBaseline, started == nil { started = timestamp }
        if angle >= 150 {
            stableExtended += 1; stableFlexed = 0
            guard stableExtended >= 3 else { return observation }
            if case .rep = detector.process(Self.landmarks(a, b, c), at: timestamp),
               let start = started, (0.6...10).contains(timestamp - start) {
                observation.count += 1; observation.lastDuration = timestamp - start
            }
            started = nil; hasBaseline = true
        } else if angle <= 65 {
            stableFlexed += 1; stableExtended = 0
            if stableFlexed >= 3, hasBaseline { detector.process(Self.landmarks(a, b, c), at: timestamp) }
        } else { stableExtended = 0; stableFlexed = 0 }
        return observation
    }
    private func invalidate() {
        if hasBaseline { observation.dropouts += 1 }
        detector.reset(); hasBaseline = false; started = nil
        stableExtended = 0; stableFlexed = 0; observation.angle = nil
    }
    private static func landmarks(_ a: PosePoint, _ b: PosePoint, _ c: PosePoint) -> PoseLandmarks {
        // Pixel coordinates preserve aspect ratio; normalized image x/y do not.
        PoseLandmarks(points: [.rightShoulder: CGPoint(x: a.x, y: a.y),
                               .rightElbow: CGPoint(x: b.x, y: b.y),
                               .rightWrist: CGPoint(x: c.x, y: c.y)])
    }
    public static func angle(_ a: PosePoint, _ b: PosePoint, _ c: PosePoint) -> Double? {
        landmarks(a, b, c).elbowAngle(.right)
    }
}

/// Vision input validation lives beside the SDK adapter, not in the app service.
/// The SDK's convenience pixel-buffer API selects the first body and uses
/// anisotropic normalized coordinates, so use its landmark API instead.
public final class CameraRepTracker {
    private let counter = CurlCounter()
    public private(set) var modelRevision = 0
    public var observation: RepObservation { counter.observation }
    public init() {}
    public func reset() { counter.reset() }
    public func process(_ buffer: CVPixelBuffer, timestamp: TimeInterval) -> RepObservation {
        let request = VNDetectHumanBodyPoseRequest()
        modelRevision = request.revision
        do {
            try VNImageRequestHandler(cvPixelBuffer: buffer, orientation: .up).perform([request])
            guard let bodies = request.results, bodies.count == 1, let body = bodies.first else {
                var result = counter.consume(shoulder: nil, elbow: nil, wrist: nil, timestamp: timestamp)
                result.status = "Unassessed - need exactly one visible person"
                return result
            }
            let points = try body.recognizedPoints(.all)
            func point(_ key: VNHumanBodyPoseObservation.JointName) -> PosePoint? {
                guard let point = points[key] else { return nil }
                return PosePoint(x: point.x * Double(CVPixelBufferGetWidth(buffer)),
                                 y: point.y * Double(CVPixelBufferGetHeight(buffer)), confidence: Double(point.confidence))
            }
            return counter.consume(shoulder: point(.rightShoulder), elbow: point(.rightElbow), wrist: point(.rightWrist), timestamp: timestamp)
        } catch {
            var result = counter.consume(shoulder: nil, elbow: nil, wrist: nil, timestamp: timestamp)
            result.status = "Vision unavailable; no measurement produced"
            return result
        }
    }
}

public struct Benchmark: Equatable {
    public private(set) var latencies: [Double] = []
    public private(set) var processedFrames = 0
    public init() {}
    public mutating func record(milliseconds: Double) {
        guard milliseconds.isFinite, milliseconds >= 0 else { return }
        processedFrames += 1; latencies.append(milliseconds)
        if latencies.count > 300 { latencies.removeFirst() }
    }
    public func percentile(_ fraction: Double) -> Double? {
        guard !latencies.isEmpty else { return nil }
        let sorted = latencies.sorted()
        let index = Int((Double(sorted.count - 1) * max(0, min(1, fraction))).rounded(.up))
        return sorted[index]
    }
}
