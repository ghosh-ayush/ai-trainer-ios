import XCTest
@testable import AITrainerCore

final class IntegrationTests: XCTestCase {
    let core = LocalPythonTrainerService(transport: EmbeddedPythonTransport())
    func testCatalogIsDescriptiveAndDoesNotChangeGovernedContent() throws {
        let library = ContentLibrary(permitsFixtures: true)
        let before = library.exercises
        let catalog = try ExerciseCatalog.bundled(core: core)
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
        XCTAssertThrowsError(try ExerciseCatalog(data: data, core: core))
    }

    // Comparable-history ordering is covered by `test_comparable_sessions_filter_and_order`
    // in core/python/tests/test_domain.py; Swift no longer has a history view of its own.

    func testPainGateBeatsQualifyingHistoryThroughTheCore() {
        let fixtures = TrainerTests()
        var state = fixtures.qualified()
        XCTAssertEqual(fixtures.decision(state).reason, "QUALIFYING_EXPOSURES_COMPLETE")
        state.painExclusions.insert("bench")
        XCTAssertEqual(fixtures.decision(state).reason, "REPORTED_PAIN")
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
