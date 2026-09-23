import Foundation
import PythonBridge

/// The sole domain transport seam: JSON bytes in, JSON bytes out.
public protocol TrainerCoreTransport {
    func exchange(_ request: Data) throws -> Data
}

public final class EmbeddedPythonTransport: TrainerCoreTransport {
    private static let lock = NSLock()
    public init() {}
    public func exchange(_ request: Data) throws -> Data {
        Self.lock.lock(); defer { Self.lock.unlock() }
        #if os(iOS)
        let home = Bundle.main.bundleURL.appendingPathComponent("python").path
        let path = Bundle.main.bundleURL.appendingPathComponent("app").path
        #else
        let home = ProcessInfo.processInfo.environment["AI_TRAINER_PYTHON_HOME"] ?? ""
        guard let path = ProcessInfo.processInfo.environment["AI_TRAINER_PYTHON_PATH"] else {
            throw TrainerError.invalid("Set AI_TRAINER_PYTHON_PATH to core/python for desktop tests.")
        }
        #endif
        if let error = trainer_python_initialize(home, path) {
            defer { trainer_python_free(error) }
            throw TrainerError.invalid(String(cString: error))
        }
        var error: UnsafeMutablePointer<CChar>?
        guard let input = String(data: request, encoding: .utf8) else { throw TrainerError.invalid("Invalid UTF-8 request.") }
        let output = trainer_python_call(input, &error)
        defer { trainer_python_free(output); trainer_python_free(error) }
        guard let output else { throw TrainerError.invalid(error.map { String(cString: $0) } ?? "Local Python failed.") }
        return Data(String(cString: output).utf8)
    }
}

/// In-process calls into the Python core; no sockets, subprocesses, downloads or remote fallback.
///
/// The app composes exactly one instance at startup (`AppStore`) and hands it to everything that
/// needs the domain core. There is deliberately no shared singleton: tests build their own, with
/// a failing or recording transport where needed.
public final class LocalPythonTrainerService {
    private let transport: any TrainerCoreTransport
    public init(transport: any TrainerCoreTransport) { self.transport = transport }

    /// Runs `operation` with an encoded `payload` and decodes its result.
    public func call<P: Encodable, R: Decodable>(_ operation: String, _ payload: P, as: R.Type = R.self) throws -> R {
        try send(operation, payload: JSONEncoder().encode(payload))
    }
    /// The bundled content the core runs against. Also the startup probe that Python is alive.
    public func library(permitsFixtures: Bool) throws -> ContentLibrary {
        try call("library", ["permitsFixtures": permitsFixtures])
    }
    /// Upgrades a saved state file. The bytes go to Python untouched, so Swift never
    /// reinterprets a field from an older version before it has been migrated.
    public func migrate(savedState: Data) throws -> AthleteState {
        try send("migrateState", payload: Data(#"{"state":"#.utf8) + savedState + Data("}".utf8))
    }

    private struct Response<Result: Decodable>: Decodable {
        struct Failure: Decodable { let code: String; let message: String }
        let schemaVersion: String
        let result: Result?
        let error: Failure?
    }
    private func send<R: Decodable>(_ operation: String, payload: Data) throws -> R {
        let envelope = Data(#"{"schemaVersion":"1.0","operation":""#.utf8) + Data(operation.utf8)
            + Data(#"","payload":"#.utf8) + payload + Data("}".utf8)
        let response = try JSONDecoder().decode(Response<R>.self, from: transport.exchange(envelope))
        guard response.schemaVersion == "1.0" else { throw TrainerError.unsupported }
        if let error = response.error {
            switch error.code {
            case "notFound": throw TrainerError.notFound
            case "conflict": throw TrainerError.conflict
            case "staleProposal": throw TrainerError.staleProposal
            case "unsupported": throw TrainerError.unsupported
            default: throw TrainerError.invalid(error.message)
            }
        }
        guard let result = response.result else { throw TrainerError.invalid("Missing local core result.") }
        return result
    }
}
