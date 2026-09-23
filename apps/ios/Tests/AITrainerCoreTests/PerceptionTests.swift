import XCTest
@testable import AITrainerCore

/// Per-frame perception and timers stay in Swift; so do their tests.
final class PerceptionTests: XCTestCase {
    let shoulder = PosePoint(x: 0, y: 1, confidence: 1)
    let elbow = PosePoint(x: 0, y: 0, confidence: 1)
    let extended = PosePoint(x: 0, y: -1, confidence: 1)
    let flexed = PosePoint(x: 0.5, y: 1, confidence: 1)

    func feed(_ counter: CurlCounter, _ wrist: PosePoint?, at time: Double) {
        _ = counter.consume(shoulder: wrist == nil ? nil : shoulder, elbow: wrist == nil ? nil : elbow, wrist: wrist, timestamp: time)
    }
    func testFullCycleCountsOne() {
        let counter = CurlCounter()
        for i in 0..<12 { feed(counter, (4..<8).contains(i) ? flexed : extended, at: Double(i) * 0.1) }
        XCTAssertEqual(counter.observation.count, 1)
        XCTAssertNotNil(counter.observation.lastDuration)
    }
    func testDropoutCannotProducePhantomRep() {
        let counter = CurlCounter()
        for t in [0.0, 0.1, 0.2] { feed(counter, extended, at: t) }
        for t in [0.3, 0.4, 0.5] { feed(counter, flexed, at: t) }
        feed(counter, nil, at: 0.6)
        for t in [0.7, 0.8, 0.9] { feed(counter, extended, at: t) }
        XCTAssertEqual(counter.observation.count, 0)
    }
    func testGapRejectsPartialCycleAndKeepsCompletedCount() {
        let counter = CurlCounter()
        for i in 0..<12 { feed(counter, (4..<8).contains(i) ? flexed : extended, at: Double(i) * 0.1) }
        XCTAssertEqual(counter.observation.count, 1)
        for i in 12..<16 { feed(counter, flexed, at: Double(i) * 0.1) }
        for i in 25..<29 { feed(counter, extended, at: Double(i) * 0.1) }
        XCTAssertEqual(counter.observation.count, 1)
        XCTAssertEqual(counter.observation.dropouts, 1)
        let before = counter.observation
        feed(counter, flexed, at: 2)
        feed(counter, flexed, at: .nan)
        XCTAssertEqual(counter.observation, before)
        counter.reset()
        for i in 0..<8 { feed(counter, i < 4 ? flexed : extended, at: Double(i) * 0.1) }
        XCTAssertEqual(counter.observation.count, 0)
    }
    func testBenchmarkReportsMeasuredPercentile() {
        var benchmark = Benchmark()
        [10.0, 20, 30, 40, 50].forEach { benchmark.record(milliseconds: $0) }
        XCTAssertEqual(benchmark.percentile(0.5), 30)
        XCTAssertEqual(benchmark.percentile(0.95), 50)
    }
    func testRestTimerIsDeadlineBasedAndSurvivesPersistence() throws {
        let now = Date(timeIntervalSinceReferenceDate: 811_382_400)
        let plan = SessionPlan(name: "Plan", slots: [])
        var session = WorkoutSession(programID: UUID(), programRevision: 1, originalPlan: plan, plan: plan,
                                     status: .paused, startedAt: now, timeZone: "UTC", checkIn: CheckIn(), restEndsAt: now.addingTimeInterval(120))
        let restored = try JSONDecoder().decode(WorkoutSession.self, from: JSONEncoder().encode(session))
        let activity = try XCTUnwrap(WorkoutActivity(session: restored))
        XCTAssertEqual(activity.remainingRestSeconds(at: now.addingTimeInterval(60.1)), 60)
        XCTAssertEqual(activity.remainingRestSeconds(at: now.addingTimeInterval(121)), 0)
        session.status = .completed
        XCTAssertNil(WorkoutActivity(session: session))
    }
}
