import Foundation

public protocol StatePersistence: AnyObject {
    func load() throws -> Data?
    func save(_ data: Data) throws
}
public final class MemoryPersistence: StatePersistence {
    public var data: Data?
    public var failWrites = false
    public init(data: Data? = nil) { self.data = data }
    public func load() throws -> Data? { data }
    public func save(_ data: Data) throws {
        if failWrites { throw TrainerError.invalid("Simulated persistence failure") }
        self.data = data
    }
}
public final class FilePersistence: StatePersistence {
    private let url: URL
    public init(url: URL) throws {
        self.url = url
        let directory = url.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        #if os(iOS)
        try FileManager.default.setAttributes([.protectionKey: FileProtectionType.complete], ofItemAtPath: directory.path)
        var excluded = directory
        var values = URLResourceValues(); values.isExcludedFromBackup = true
        try excluded.setResourceValues(values)
        #endif
    }
    public func load() throws -> Data? {
        guard FileManager.default.fileExists(atPath: url.path) else { return nil }
        return try Data(contentsOf: url)
    }
    public func save(_ data: Data) throws {
        #if os(iOS)
        try data.write(to: url, options: [.atomic, .completeFileProtection])
        #else
        try data.write(to: url, options: .atomic)
        #endif
    }
}
/// Single-process, serialized transactions. Candidate state is published only after durable save.
public final class StateRepository {
    private let lock = NSRecursiveLock()
    private let persistence: StatePersistence
    private var state: AthleteState
    public init(persistence: StatePersistence) throws {
        self.persistence = persistence
        if let data = try persistence.load() {
            do {
                let loaded = try JSONDecoder().decode(AthleteState.self, from: data)
                guard loaded.schemaVersion == 1 else { throw TrainerError.corruptStore }
                state = loaded
            } catch { throw TrainerError.corruptStore }
        } else { state = AthleteState() }
    }
    public var snapshot: AthleteState {
        lock.lock(); defer { lock.unlock() }; return state
    }
    @discardableResult public func transaction<T>(_ operation: (inout AthleteState) throws -> T) throws -> T {
        lock.lock(); defer { lock.unlock() }
        var candidate = state
        let result = try operation(&candidate)
        candidate.revision += 1
        let data = try JSONEncoder().encode(candidate)
        try persistence.save(data)
        state = candidate
        return result
    }
    public func export() throws -> Data {
        let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return try encoder.encode(snapshot)
    }
    public func deleteAll() throws {
        // No restore/import or cloud backup endpoint exists in this implementation.
        try transaction { $0 = AthleteState() }
    }
}
