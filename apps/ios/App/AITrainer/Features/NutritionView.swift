import SwiftUI
import AITrainerCore

/// P31 / P30 Meal logging (Developer ▸ Labs): user-confirmed estimates with an audit trail.
struct NutritionView: View {
    @EnvironmentObject private var store: AppStore
    @State private var showNew = false
    @State private var selectedMeal: Meal?
    @State private var selectedRecipe: Recipe?
    var body: some View {
        DetailScreen("P4 meal logging") {
            let total = Meal.total(store.state.meals, on: Date())
            StitchSectionLabel("Today's confirmed estimates")
            StitchCard {
                StitchStat("Energy", value: number(total.calories), unit: "kcal")
                StitchKeyValue("Protein · carbs · fat", value: "\(number(total.protein)) · \(number(total.carbs)) · \(number(total.fat)) g")
                StitchFootnote("These are estimates you enter and confirm. No food-photo accuracy or training adaptation is implied.")
            }
            Button("Log a meal") { showNew = true }.buttonStyle(.stitch())
            if !store.state.recipes.isEmpty {
                StitchSectionLabel("Reusable portions")
                ForEach(store.state.recipes) { recipe in
                    Button { selectedRecipe = recipe } label: {
                        StitchListRow(recipe.name, subtitle: "\(number(recipe.perServing.calories)) kcal per portion", symbol: "takeoutbag.and.cup.and.straw")
                    }
                    .buttonStyle(.plain)
                }
            }
            StitchSectionLabel("Meal history", meta: "Newest first")
            if store.state.meals.isEmpty {
                StitchCard("No meals yet", body: "Logged estimates appear here. Nothing is imported or inferred.")
            }
            ForEach(store.state.meals.sorted { $0.occurredAt > $1.occurredAt }) { meal in
                Button { selectedMeal = meal } label: {
                    StitchListRow(meal.name, subtitle: "\(number(meal.nutrients.calories)) kcal · \(meal.occurredAt.formatted(date: .abbreviated, time: .shortened))", symbol: "fork.knife")
                }
                .buttonStyle(.plain)
            }
        }
        .sheet(isPresented: $showNew) { MealEditor() }
        .sheet(item: $selectedMeal) { MealEditor(existing: $0) }
        .sheet(item: $selectedRecipe) { RecipePortionView(recipe: $0) }
    }
}

/// P32 / P33 / P46: new meal, correct meal, delete meal.
struct MealEditor: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    var existing: Meal? = nil
    @State private var name = ""
    @State private var calories = ""
    @State private var protein = ""
    @State private var carbs = ""
    @State private var fat = ""
    @State private var date = Date()
    @State private var saveRecipe = false
    @State private var confirmed = false
    @State private var confirmDelete = false
    var body: some View {
        Group {
            StitchSectionLabel("Estimate for this entire portion")
            field("Meal name", text: $name, keyboard: .default)
            field("Calories (kcal)", text: $calories, keyboard: .decimalPad)
            field("Protein (g)", text: $protein, keyboard: .decimalPad)
            field("Carbohydrate (g)", text: $carbs, keyboard: .decimalPad)
            field("Fat (g)", text: $fat, keyboard: .decimalPad)
            StitchField("Eaten at", value: date.formatted(date: .abbreviated, time: .shortened)) {
                DatePicker("Eaten at", selection: $date).labelsHidden()
            }
            StitchToggleField("Save as one reusable portion", isOn: $saveRecipe, on: "Save", off: "Don't save")
            StitchToggleField("I confirm these are estimates for my portion", isOn: $confirmed, on: "Confirmed", off: "Not confirmed")
            Button(existing == nil ? "Save meal" : "Save correction") { save() }.buttonStyle(.stitch()).disabled(!confirmed)
            if existing != nil {
                Button("Delete meal", role: .destructive) { confirmDelete = true }.buttonStyle(.stitch(.destructive))
            }
        }
        .stitchSheet(existing == nil ? "New meal" : "Correct meal") { dismiss() }
        .confirmationDialog("Delete this meal estimate?", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("Delete", role: .destructive) {
                guard let existing else { return }
                store.perform({ try $0.deleteMeal(id: existing.id) }) { _ in dismiss() }
            }
        }
        .onAppear {
            if let existing {
                name = existing.name; calories = number(existing.nutrients.calories); protein = number(existing.nutrients.protein)
                carbs = number(existing.nutrients.carbs); fat = number(existing.nutrients.fat); date = existing.occurredAt
            }
        }
    }
    private func field(_ label: String, text: Binding<String>, keyboard: UIKeyboardType) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).stitch(.monoLabel).textCase(.uppercase).foregroundStyle(Stitch.textMuted)
            TextField(label, text: text).keyboardType(keyboard).stitch(.monoBody).foregroundStyle(Stitch.textPrimary)
        }
        .padding(.horizontal, 16).padding(.vertical, 14).glass(radius: 8)
    }
    private func save() {
        store.perform({ service in
            guard let energy = try parseOptionalNumber(calories), let p = try parseOptionalNumber(protein),
                  let c = try parseOptionalNumber(carbs), let f = try parseOptionalNumber(fat) else {
                throw TrainerError.invalid("Enter each nutrient estimate explicitly, including known zero values.")
            }
            var meal = existing ?? Meal(name: name, nutrients: Nutrients())
            meal.name = name; meal.nutrients = Nutrients(calories: energy, protein: p, carbs: c, fat: f); meal.occurredAt = date
            try service.saveMeal(meal, asRecipe: saveRecipe)
        }) { _ in dismiss() }
    }
}

/// P34: log a saved portion scaled by servings (scaling runs in the core).
struct RecipePortionView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    let recipe: Recipe
    @State private var servings = 1.0
    var body: some View {
        Group {
            StitchSectionLabel(recipe.name, meta: "Saved portion")
            StitchField("Saved portions", value: number(servings)) {
                StitchStepperButtons(decrement: { servings = max(0.5, servings - 0.5) }, increment: { servings = min(10, servings + 0.5) })
            }
            StitchStat("Estimated energy", value: number(recipe.perServing.calories * servings), unit: "kcal")
            Button("Confirm portion and log") {
                store.perform({ service in
                    try service.saveMeal(Meal(name: recipe.name, nutrients: try service.scaleNutrients(recipe.perServing, servings: servings)))
                }) { _ in dismiss() }
            }
            .buttonStyle(.stitch())
        }
        .stitchSheet("Reuse a portion") { dismiss() }
    }
}
