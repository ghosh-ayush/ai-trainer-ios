import XCTest
@testable import AITrainerCore

/// The Swift side of the bridge: transport, envelope handling and the interpreter lock.
/// Domain rules are tested in `core/python/tests`.
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
    func testVersionMismatchIsRejected() throws {
        struct WrongVersion: TrainerCoreTransport {
            func exchange(_ request: Data) throws -> Data { Data(#"{"schemaVersion":"2.0","result":true}"#.utf8) }
        }
        let core = LocalPythonTrainerService(transport: WrongVersion())
        XCTAssertThrowsError(try core.call("test", [String: String](), as: Bool.self)) { XCTAssertEqual($0 as? TrainerError, .unsupported) }
    }
}
