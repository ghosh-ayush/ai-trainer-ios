import Foundation
import PythonBridge

/// The sole domain transport seam. A future remote implementation exchanges the same DTOs.
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

public struct CoreRequest<Payload: Encodable>: Encodable {
    public let schemaVersion = "1.0"
    public let operation: String
    public let payload: Payload
    public init(operation: String, payload: Payload) { self.operation = operation; self.payload = payload }
}
private struct CoreResponse<Result: Decodable>: Decodable {
    struct Failure: Decodable { let code: String; let message: String }
    let schemaVersion: String
    let result: Result?
    let error: Failure?
}
struct LibraryDTO: Encodable {
    let exercises: [Exercise]; let policy: TrainingPolicy; let permitsFixtures: Bool
    init(_ library: ContentLibrary) { exercises = library.exercises; policy = library.policy; permitsFixtures = library.permitsFixtures }
}
struct TrainingRequestDTO: Encodable {
    let kind: String
    var slotID: UUID?; var alternativeID: String?; var minutes: Int?; var date: Date?
    init(_ request: Request) {
        switch request {
        case .progression(let id): kind = "progression"; slotID = id
        case .shorten(let value): kind = "shorten"; minutes = value
        case .substitute(let id, let alternative): kind = "substitute"; slotID = id; alternativeID = alternative
        case .reschedule(let value): kind = "reschedule"; date = value
        }
    }
}

/// Transport-independent domain service interface.
public protocol TrainerDomainService {
    func call<P: Encodable, R: Decodable>(_ operation: String, _ payload: P, as: R.Type) throws -> R
}

/// In-process JSON calls; no sockets, subprocesses, downloads or remote fallback.
public final class LocalPythonTrainerService: TrainerDomainService {
    public static let shared = LocalPythonTrainerService(transport: EmbeddedPythonTransport())
    private let transport: any TrainerCoreTransport
    public init(transport: any TrainerCoreTransport) { self.transport = transport }
    public func call<P: Encodable, R: Decodable>(_ operation: String, _ payload: P, as: R.Type = R.self) throws -> R {
        let encoder = JSONEncoder(); encoder.dateEncodingStrategy = .deferredToDate
        let decoder = JSONDecoder(); decoder.dateDecodingStrategy = .deferredToDate
        let data = try transport.exchange(encoder.encode(CoreRequest(operation: operation, payload: payload)))
        let response = try decoder.decode(CoreResponse<R>.self, from: data)
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

struct CoreRecommendationResult: Decodable { let state: AthleteState; let decision: Decision? }

private struct DecisionPayload: Encodable { let state: AthleteState; let request: TrainingRequestDTO; let library: LibraryDTO; let now: Date }
private struct ProgressionPayload: Encodable { let state: AthleteState; let plan: SessionPlan; let slot: Prescription; let policy: TrainingPolicy; let now: Date }
private struct InitialProgramPayload: Encodable { let profile: Profile; let library: LibraryDTO; let now: Date; let ids: [UUID] }
private struct RecommendationPayload: Encodable {
    let operation: String; let state: AthleteState; let request: TrainingRequestDTO?
    let id: UUID?; let reason: String?; let library: LibraryDTO; let now: Date; let ids: [UUID]
}
private struct NutrientsPayload: Encodable { let nutrients: Nutrients; let servings: Double }

extension TrainerDomainService {
    public func call<P: Encodable, R: Decodable>(_ operation: String, _ payload: P) throws -> R {
        try call(operation, payload, as: R.self)
    }
    func decide(state: AthleteState, request: Request, library: ContentLibrary, now: Date) throws -> Decision {
        return try call("decide", DecisionPayload(state: state, request: TrainingRequestDTO(request), library: LibraryDTO(library), now: now))
    }
    func progression(state: AthleteState, plan: SessionPlan, slot: Prescription, policy: TrainingPolicy, now: Date) throws -> Decision {
        return try call("progression", ProgressionPayload(state: state, plan: plan, slot: slot, policy: policy, now: now))
    }
    func initialProgram(profile: Profile, library: ContentLibrary, now: Date) throws -> Program {
        return try call("initialProgram", InitialProgramPayload(profile: profile, library: LibraryDTO(library), now: now, ids: (0..<6).map { _ in UUID() }))
    }
    func recommendation(_ operation: String, state: AthleteState, request: Request? = nil, id: UUID? = nil,
                        reason: String? = nil, library: ContentLibrary, now: Date) throws -> CoreRecommendationResult {
        let selected = request ?? state.recommendations.first { $0.id == id }?.request
        return try call("recommendation", RecommendationPayload(operation: operation, state: state, request: selected.map(TrainingRequestDTO.init),
            id: id, reason: reason, library: LibraryDTO(library), now: now, ids: [UUID(), UUID()]))
    }
    func nutrients(_ nutrients: Nutrients, servings: Double = 1) throws -> Nutrients {
        return try call("nutrients", NutrientsPayload(nutrients: nutrients, servings: servings))
    }
}
