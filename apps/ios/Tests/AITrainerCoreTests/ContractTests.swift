import XCTest
@testable import AITrainerCore

final class ContractTests: XCTestCase {
    private var fixtures: URL {
        URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("shared/fixtures/v1")
    }
    func testRealEmbeddedRuntimeMatchesSharedGoldenContract() throws {
        let request = try Data(contentsOf: fixtures.appendingPathComponent("qualifying-request.json"))
        let expected = try Data(contentsOf: fixtures.appendingPathComponent("qualifying-response.json"))
        let actual = try EmbeddedPythonTransport().exchange(request)
        XCTAssertEqual(try JSONSerialization.jsonObject(with: actual) as? NSDictionary,
                       try JSONSerialization.jsonObject(with: expected) as? NSDictionary)
    }
    func testTransportFailureCannotPublishOrSaveCandidate() throws {
        struct OfflineFailure: TrainerCoreTransport {
            func exchange(_ request: Data) throws -> Data { throw TrainerError.unsupported }
        }
        let storage = MemoryPersistence()
        let repository = try StateRepository(persistence: storage)
        let before = repository.snapshot
        let service = TrainerService(repository: repository, library: ContentLibrary(permitsFixtures: true),
                                     core: LocalPythonTrainerService(transport: OfflineFailure()))
        XCTAssertThrowsError(try service.request(.shorten(30)))
        XCTAssertEqual(repository.snapshot, before)
        XCTAssertNil(storage.data)
    }
    func testVersionMismatchIsRejected() throws {
        struct WrongVersion: TrainerCoreTransport {
            func exchange(_ request: Data) throws -> Data { Data(#"{"schemaVersion":"2.0","result":true}"#.utf8) }
        }
        let core = LocalPythonTrainerService(transport: WrongVersion())
        XCTAssertThrowsError(try core.call("test", [String: String](), as: Bool.self)) { XCTAssertEqual($0 as? TrainerError, .unsupported) }
    }
    func testSubsecondAuditDateSurvivesCoreRoundTripExactly() throws {
        let fixtures = TrainerTests()
        var state = fixtures.qualified()
        state.sessions[0].checkIn.occurredAt = Date(timeIntervalSinceReferenceDate: 811_382_400.1234567)
        let service = try fixtures.service(state)
        try service.exclude(exerciseID: "db_curl", excluded: true)
        XCTAssertEqual(service.repository.snapshot.sessions, state.sessions)
    }
    func testConcurrentCallsUseOneInterpreterSafely() throws {
        let request = try Data(contentsOf: fixtures.appendingPathComponent("qualifying-request.json"))
        let expected = try EmbeddedPythonTransport().exchange(request)
        let lock = NSLock()
        var results: [Data] = []
        DispatchQueue.concurrentPerform(iterations: 20) { _ in
            let value = try? EmbeddedPythonTransport().exchange(request)
            lock.lock(); if let value { results.append(value) }; lock.unlock()
        }
        XCTAssertEqual(results.count, 20)
        XCTAssertTrue(results.allSatisfy { $0 == expected })
    }
    func testFailedSaveRollsBackPythonRecommendationAcceptance() throws {
        let fixtures = TrainerTests(), storage = MemoryPersistence()
        let service = try fixtures.service(fixtures.qualified(), storage: storage)
        let slot = try XCTUnwrap(service.repository.snapshot.nextPlan?.slots.first)
        _ = try service.request(.progression(slot.id), now: fixtures.now)
        let before = service.repository.snapshot
        storage.failWrites = true
        XCTAssertThrowsError(try service.acceptRecommendation(id: before.recommendations[0].id, now: fixtures.now))
        XCTAssertEqual(service.repository.snapshot, before)
    }
}
