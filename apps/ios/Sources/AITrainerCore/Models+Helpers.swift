import Foundation

// Read-only presentation helpers on top of the generated records in Models.swift.
// No rules live here: every decision, validation and mutation runs in `core/python`.

public enum TrainerError: Error, LocalizedError, Equatable {
    case invalid(String), notFound, conflict, staleProposal, unsupported, corruptStore
    public var errorDescription: String? {
        switch self {
        case .invalid(let message): return message
        case .notFound: return "The requested record no longer exists."
        case .conflict: return "This record changed. Review the conflicting versions before continuing."
        case .staleProposal: return "The evidence or plan changed. Request a fresh preview."
        case .unsupported: return "No enabled, reviewed policy supports this request."
        case .corruptStore: return "Saved data could not be read. It has not been overwritten."
        }
    }
}

extension TrainingRequest {
    public static func progression(_ slotID: UUID) -> TrainingRequest { .init(kind: "progression", slotID: slotID) }
    public static func shorten(_ minutes: Int) -> TrainingRequest { .init(kind: "shorten", minutes: minutes) }
    public static func substitute(_ slotID: UUID, _ alternativeID: String) -> TrainingRequest {
        .init(kind: "substitute", slotID: slotID, alternativeID: alternativeID)
    }
    public static func reschedule(_ date: Date) -> TrainingRequest { .init(kind: "reschedule", date: date) }
    /// ADR-018: a week fitted to the sessions the athlete has actually been completing. `utcOffset`
    /// (seconds from UTC) lets the core read which weekdays they train on in their own time zone.
    public static func replan(utcOffset: Int) -> TrainingRequest { .init(kind: "replan", utcOffset: utcOffset) }
    /// ADR-025: new free days (and minutes), proposed as the chosen week; `optionID` from `weekOptions`.
    public static func changeDays(_ freeDays: [Int], minutes: Int?, optionID: String?) -> TrainingRequest {
        .init(kind: "changeDays", minutes: minutes, freeDays: freeDays, optionID: optionID)
    }
}

extension ContentLibrary {
    public func exercise(_ id: String) -> Exercise? { exercises.first { $0.id == id } }
}

extension MassUnit: Identifiable {
    public var id: String { rawValue }
}

extension LoadBasis {
    public var label: String {
        switch self {
        case .total: return "Total load"
        case .perHand: return "Per dumbbell"
        case .machineSetting: return "Machine setting"
        case .assistance: return "Assistance"
        case .externalBodyweight: return "Added external load"
        }
    }
}

extension SessionPlan {
    public var estimatedMinutes: Int { warmUpMinutes + slots.reduce(0) { $0 + $1.estimatedMinutes } }
}

extension WorkoutSession {
    public var active: Bool { status == .inProgress || status == .paused }
    public var completeWorkingSets: Int { logs.filter { $0.kind == .working }.count }
}

extension AthleteState {
    public var activeSession: WorkoutSession? { sessions.last(where: \.active) }
    /// A temporary override wins over the program's sequenced plan (as in `athlete_state.next_plan`).
    public var nextPlan: SessionPlan? {
        if let nextPlanOverride { return nextPlanOverride }
        guard let program, program.plans.indices.contains(program.sequenceIndex) else { return nil }
        return program.plans[program.sequenceIndex]
    }
}

extension Nutrients {
    public static func + (a: Nutrients, b: Nutrients) -> Nutrients {
        Nutrients(calories: a.calories + b.calories, protein: a.protein + b.protein, carbs: a.carbs + b.carbs, fat: a.fat + b.fat)
    }
}

extension Meal {
    /// Sum of confirmed estimates eaten on `date` in the device calendar.
    public static func total(_ meals: [Meal], on date: Date, calendar: Calendar = .current) -> Nutrients {
        meals.filter { calendar.isDate($0.occurredAt, inSameDayAs: date) }.reduce(Nutrients()) { $0 + $1.nutrients }
    }
}

extension StatusKind {
    /// How a training status reads in the app (ADR-019).
    public var label: String {
        switch self {
        case .onBreak: return "On a break"
        case .sick: return "Sick"
        case .injured: return "Injured"
        }
    }
}

extension ContentLibrary {
    /// The exercise's movement role in words, as the content bundle names it ("KD" reads "Squat").
    /// Roles the bundle doesn't name (older content) read as they are; nil for an unknown exercise.
    public func roleName(of exerciseID: String) -> String? {
        guard let role = exercise(exerciseID)?.role else { return nil }
        return roleNames[role] ?? role
    }
}

/// Names for the core's weekdays, 0-6 with Monday = 0 (ADR-017).
public enum Weekday {
    public static let initials = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    public static let shortNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    public static let names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    /// Today's weekday in the core's numbering (Monday = 0), in `calendar`'s time zone.
    public static func today(_ calendar: Calendar = .current, now: Date = Date()) -> Int {
        (calendar.component(.weekday, from: now) + 5) % 7  // Calendar: Sunday = 1 … Saturday = 7
    }
    public static func initial(_ day: Int) -> String {
        initials.indices.contains(day) ? initials[day] : "\(day + 1)"
    }
    public static func short(_ day: Int) -> String {
        shortNames.indices.contains(day) ? shortNames[day] : "Day \(day + 1)"
    }
    public static func name(_ day: Int) -> String {
        names.indices.contains(day) ? names[day] : "Day \(day + 1)"
    }
}
