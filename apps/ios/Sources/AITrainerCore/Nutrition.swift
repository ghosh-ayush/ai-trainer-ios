import Foundation

// Behaviour for the generated Nutrients / Meal / Recipe / MealAudit records (see Models.swift).

extension Nutrients {
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

extension Meal {
    /// Sum of confirmed estimates eaten on `date` in the device calendar.
    public static func total(_ meals: [Meal], on date: Date, calendar: Calendar = .current) -> Nutrients {
        meals.filter { calendar.isDate($0.occurredAt, inSameDayAs: date) }.reduce(Nutrients()) { $0 + $1.nutrients }
    }
}
