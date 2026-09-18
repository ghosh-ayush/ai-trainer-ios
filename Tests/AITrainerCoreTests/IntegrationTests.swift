import XCTest
@testable import AITrainerCore

final class IntegrationTests: XCTestCase {
    func testCatalogIsDescriptiveAndDoesNotChangeGovernedContent() throws {
        let library = ContentLibrary(permitsFixtures: true)
        let before = library.exercises
        let catalog = try ExerciseCatalog.bundled()
        XCTAssertEqual(catalog.exercises.count, 876)
        XCTAssertEqual(Set(catalog.exercises.map(\.id)).count, catalog.exercises.count)
        for (governed, upstream) in ExerciseCatalog.governedLinks {
            XCTAssertNotNil(catalog.exercise(upstream))
            XCTAssertEqual(catalog.description(for: try XCTUnwrap(library.exercise(governed)))?.id, upstream)
        }
        XCTAssertEqual(library.exercises, before)
        XCTAssertNil(library.exercise(catalog.exercises[0].id))
        XCTAssertNil(catalog.description(for: try XCTUnwrap(library.exercise("db_row"))))
        XCTAssertTrue(try ThirdPartyNotices.text().contains("Copyright (c) 2026 Nazar Kozak"))
    }

    func testCatalogRejectsDuplicateIDs() throws {
        let record = #"{"id":"duplicate","name":"Example","level":"beginner","primaryMuscles":[],"secondaryMuscles":[],"instructions":[],"category":"strength","images":[]}"#
        let data = "[\(record),\(record)]".data(using: .utf8)!
        XCTAssertThrowsError(try ExerciseCatalog(data: data))
    }

    func testPerformanceHistoryFiltersAndOrdersComparableSessions() {
        let fixtures = TrainerTests()
        var state = fixtures.fixture()
        let older = fixtures.exposure(state, daysAgo: 5)
        let newer = fixtures.exposure(state, daysAgo: 1)
        var skipped = fixtures.exposure(state, daysAgo: 0); skipped.status = .skipped
        var active = fixtures.exposure(state, daysAgo: 0); active.status = .paused
        var different = fixtures.exposure(state, daysAgo: 0); different.plan.slots[0].equipment.id = "different-rack"
        let future = fixtures.exposure(state, daysAgo: -1)
        state.sessions = [older, future, skipped, active, different, newer]
        let history = PerformanceHistory(state: state, slot: state.nextPlan!.slots[0], now: fixtures.now)
        XCTAssertEqual(history.sessions.map(\.id), [newer.id, older.id])
        XCTAssertEqual(history.workingLogs(in: newer).map(\.index), [0, 1, 2])
    }

    func testInjectedPolicyCannotBypassBrainPainGate() {
        struct SentinelPolicy: ProgressionPolicy {
            func decide(state: AthleteState, plan: SessionPlan, slot: Prescription, policy: TrainingPolicy, now: Date) -> Decision {
                .init(.keepPlan, "SENTINEL", "Injected policy was called")
            }
        }
        let fixtures = TrainerTests()
        var state = fixtures.qualified()
        let brain = TrainingBrain(library: fixtures.library, progressionPolicy: SentinelPolicy())
        let request = Request.progression(state.nextPlan!.slots[0].id)
        XCTAssertEqual(brain.decide(state: state, request: request, now: fixtures.now).reason, "SENTINEL")
        state.painExclusions.insert("bench")
        XCTAssertEqual(brain.decide(state: state, request: request, now: fixtures.now).reason, "REPORTED_PAIN")
    }

    func testRestSnapshotSurvivesPersistenceAndExpiresWithoutTicks() throws {
        let fixtures = TrainerTests()
        let state = fixtures.fixture()
        var session = WorkoutSession(program: state.program!, plan: state.nextPlan!, checkIn: CheckIn(), now: fixtures.now, timeZone: "UTC")
        session.restEndsAt = fixtures.now.addingTimeInterval(120)
        session.status = .paused
        let restored = try JSONDecoder().decode(WorkoutSession.self, from: JSONEncoder().encode(session))
        let activity = try XCTUnwrap(WorkoutActivity(session: restored))
        XCTAssertEqual(activity.remainingRestSeconds(at: fixtures.now.addingTimeInterval(60.1)), 60)
        XCTAssertEqual(activity.remainingRestSeconds(at: fixtures.now.addingTimeInterval(121)), 0)
        session.status = .completed
        XCTAssertNil(WorkoutActivity(session: session))
    }

    func testSDKAdapterRejectsPartialCycleAfterGapAndRetainsCompletedCount() {
        let counter = CurlCounter()
        let shoulder = PosePoint(x: 0, y: 1, confidence: 1)
        let elbow = PosePoint(x: 0, y: 0, confidence: 1)
        let extended = PosePoint(x: 0, y: -1, confidence: 1)
        let flexed = PosePoint(x: 0.5, y: 1, confidence: 1)
        func feed(_ wrist: PosePoint, _ time: Double) {
            _ = counter.consume(shoulder: shoulder, elbow: elbow, wrist: wrist, timestamp: time)
        }
        for i in 0..<12 { feed((4..<8).contains(i) ? flexed : extended, Double(i) * 0.1) }
        XCTAssertEqual(counter.observation.count, 1)
        for i in 12..<16 { feed(flexed, Double(i) * 0.1) }
        for i in 25..<29 { feed(extended, Double(i) * 0.1) }
        XCTAssertEqual(counter.observation.count, 1)
        XCTAssertEqual(counter.observation.dropouts, 1)
        let before = counter.observation
        feed(flexed, 2)
        feed(flexed, .nan)
        XCTAssertEqual(counter.observation, before)
        counter.reset()
        for i in 0..<8 { feed(i < 4 ? flexed : extended, Double(i) * 0.1) }
        XCTAssertEqual(counter.observation.count, 0)
    }
}
