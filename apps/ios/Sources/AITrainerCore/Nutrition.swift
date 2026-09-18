import Foundation

public struct Nutrients: Codable, Equatable {
    public var calories: Double
    public var protein: Double
    public var carbs: Double
    public var fat: Double
    public init(calories: Double = 0, protein: Double = 0, carbs: Double = 0, fat: Double = 0) {
        self.calories = calories; self.protein = protein; self.carbs = carbs; self.fat = fat
    }
    public func validate() throws {
        _ = try LocalPythonTrainerService.shared.nutrients(self)
    }
    public func scaled(by servings: Double) throws -> Nutrients {
        try LocalPythonTrainerService.shared.nutrients(self, servings: servings)
    }
    public static func + (a: Nutrients, b: Nutrients) -> Nutrients {
        Nutrients(calories: a.calories + b.calories, protein: a.protein + b.protein, carbs: a.carbs + b.carbs, fat: a.fat + b.fat)
    }
}
public struct Recipe: Codable, Equatable, Identifiable {
    public var id = UUID()
    public var name: String
    public var perServing: Nutrients
    public var source = "user_estimate"
    public init(name: String, perServing: Nutrients) { self.name = name; self.perServing = perServing }
}
public struct Meal: Codable, Equatable, Identifiable {
    public var id = UUID()
    public var revision = 1
    public var name: String
    public var nutrients: Nutrients
    public var occurredAt: Date
    public var source = "user_confirmed_estimate"
    public var timeZone: String
    public init(name: String, nutrients: Nutrients, occurredAt: Date = Date(), timeZone: String = TimeZone.current.identifier) {
        self.name = name; self.nutrients = nutrients; self.occurredAt = occurredAt; self.timeZone = timeZone
    }
    public static func total(_ meals: [Meal], on date: Date, calendar: Calendar = .current) -> Nutrients {
        meals.filter { calendar.isDate($0.occurredAt, inSameDayAs: date) }.reduce(Nutrients()) { $0 + $1.nutrients }
    }
}

public struct MealAudit: Codable, Equatable, Identifiable {
    public var id = UUID()
    public var previous: Meal
    public var correctedAt: Date
}
