import Foundation

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
/// P0/P2 experiment only. Thresholds are fixtures, not validated technique/safety criteria.
/// Input points are in image-pixel coordinates, not uncorrected normalized coordinates.
public struct CurlCounter {
    private enum Position { case unknown, extended, flexed }
    private var position: Position = .unknown
    private var stableExtended = 0
    private var stableFlexed = 0
    private var started: TimeInterval?
    private var lastTimestamp: TimeInterval?
    public private(set) var observation = RepObservation()
    public init() {}
    public mutating func reset() { self = CurlCounter() }
    public mutating func consume(shoulder: PosePoint?, elbow: PosePoint?, wrist: PosePoint?, timestamp: TimeInterval) -> RepObservation {
        guard timestamp.isFinite else { return observation }
        if let last = lastTimestamp, timestamp <= last { return observation }
        if let last = lastTimestamp, timestamp - last > 0.5 { invalidate() }
        lastTimestamp = timestamp
        guard let a = shoulder, let b = elbow, let c = wrist,
              [a, b, c].allSatisfy({ $0.confidence >= 0.5 && $0.x.isFinite && $0.y.isFinite }),
              let angle = Self.angle(a, b, c) else {
            invalidate(); observation.status = "Unassessed - reposition phone"; return observation
        }
        observation.angle = angle; observation.status = "Experimental observation"
        if angle < 150, position == .extended, started == nil { started = timestamp }
        if angle >= 150 {
            stableExtended += 1; stableFlexed = 0
            if stableExtended >= 3 {
                if position == .flexed, let start = started, (0.6...10).contains(timestamp - start) {
                    observation.count += 1; observation.lastDuration = timestamp - start
                }
                started = nil
                position = .extended
            }
        } else if angle <= 65 {
            stableFlexed += 1; stableExtended = 0
            if stableFlexed >= 3, position == .extended { position = .flexed }
        } else { stableExtended = 0; stableFlexed = 0 }
        return observation
    }
    private mutating func invalidate() {
        if position != .unknown { observation.dropouts += 1 }
        position = .unknown; started = nil; stableExtended = 0; stableFlexed = 0; observation.angle = nil
    }
    public static func angle(_ a: PosePoint, _ b: PosePoint, _ c: PosePoint) -> Double? {
        let ux = a.x - b.x, uy = a.y - b.y, vx = c.x - b.x, vy = c.y - b.y
        let denominator = hypot(ux, uy) * hypot(vx, vy)
        guard denominator > 0.0001 else { return nil }
        let cosine = max(-1.0, min(1.0, (ux * vx + uy * vy) / denominator))
        return acos(cosine) * 180 / .pi
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
