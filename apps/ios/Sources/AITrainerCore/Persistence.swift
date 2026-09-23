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
/// The athlete state file on disk. On iOS the whole directory gets complete file protection, and
/// its participation in device backups (iCloud Backup, Finder/Windows backups) is the user's choice.
public final class FilePersistence: StatePersistence {
    private let url: URL
    private let directory: URL
    /// - Parameter excludedFromBackup: `true` keeps the state directory out of every device backup.
    ///   The app reads this from the "Include in iPhone backups" setting (default: included).
    public init(url: URL, excludedFromBackup: Bool) throws {
        self.url = url
        directory = url.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        #if os(iOS)
        try FileManager.default.setAttributes([.protectionKey: FileProtectionType.complete], ofItemAtPath: directory.path)
        #endif
        try setExcludedFromBackup(excludedFromBackup)
    }
    /// Applies to the directory so the state file and any future siblings follow one rule.
    /// A no-op outside iOS, where desktop test runs have no backup daemon to inform.
    public func setExcludedFromBackup(_ excluded: Bool) throws {
        #if os(iOS)
        var target = directory
        var values = URLResourceValues()
        values.isExcludedFromBackup = excluded
        try target.setResourceValues(values)
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
    /// Loads the saved file through the Python core, which upgrades older state versions.
    /// A file that cannot be read or upgraded is left on disk untouched.
    public init(persistence: StatePersistence, core: LocalPythonTrainerService) throws {
        self.persistence = persistence
        if let data = try persistence.load() {
            do { state = try core.migrate(savedState: data) } catch { throw TrainerError.corruptStore }
        } else { state = AthleteState() }
    }
    public var snapshot: AthleteState {
        lock.lock(); defer { lock.unlock() }; return state
    }
    /// Runs `operation` on a copy. A changed candidate is saved, then published; an unchanged
    /// one (for example a request answered without a proposal) touches neither disk nor revision.
    @discardableResult public func transaction<T>(_ operation: (inout AthleteState) throws -> T) throws -> T {
        lock.lock(); defer { lock.unlock() }
        var candidate = state
        let result = try operation(&candidate)
        guard candidate != state else { return result }
        candidate.revision += 1
        try persistence.save(JSONEncoder().encode(candidate))
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
