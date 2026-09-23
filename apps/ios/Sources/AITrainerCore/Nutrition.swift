import Foundation

// Behaviour for the generated Nutrients / Meal / Recipe / MealAudit records (see Models.swift).
// Validation and portion scaling live in Python (`nutrition.py`); use `TrainerService.scaleNutrients`.

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
