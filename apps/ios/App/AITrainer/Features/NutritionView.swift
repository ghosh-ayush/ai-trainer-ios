import SwiftUI
import AITrainerCore

struct NutritionView: View {
    @EnvironmentObject private var store: AppStore
    @State private var showNew = false
    @State private var selectedMeal: Meal?
    @State private var selectedRecipe: Recipe?
    var body: some View {
        List {
            Section("Today's confirmed estimates") {
                let total = Meal.total(store.state.meals, on: Date())
                Text("\(number(total.calories)) kcal").font(.largeTitle.bold())
                Text("Protein \(number(total.protein)) g · Carbs \(number(total.carbs)) g · Fat \(number(total.fat)) g")
                Text("These are estimates you enter and confirm. No food-photo accuracy or training adaptation is implied.").font(.footnote)
                Button("Log a meal") { showNew = true }
            }
            if !store.state.recipes.isEmpty {
                Section("Reusable portions") {
                    ForEach(store.state.recipes) { recipe in
                        Button(recipe.name) { selectedRecipe = recipe }
                    }
                }
            }
            Section("Meal history") {
                ForEach(store.state.meals.sorted { $0.occurredAt > $1.occurredAt }) { meal in
                    Button { selectedMeal = meal } label: {
                        VStack(alignment: .leading) {
                            Text(meal.name).font(.headline)
                            Text("\(number(meal.nutrients.calories)) kcal · \(meal.occurredAt.formatted(date: .abbreviated, time: .shortened))").font(.caption)
                        }
                    }
                }
            }
        }.navigationTitle("P4 meal logging")
        .sheet(isPresented: $showNew) { MealEditor() }
        .sheet(item: $selectedMeal) { MealEditor(existing: $0) }
        .sheet(item: $selectedRecipe) { RecipePortionView(recipe: $0) }
    }
}
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
        NavigationStack {
            Form {
                Section("Estimate for this entire portion") {
                    TextField("Meal name", text: $name)
                    TextField("Calories (kcal)", text: $calories).keyboardType(.decimalPad)
                    TextField("Protein (g)", text: $protein).keyboardType(.decimalPad)
                    TextField("Carbohydrate (g)", text: $carbs).keyboardType(.decimalPad)
                    TextField("Fat (g)", text: $fat).keyboardType(.decimalPad)
                    DatePicker("Eaten at", selection: $date)
                    Toggle("Save this amount as one reusable portion", isOn: $saveRecipe)
                    Toggle("I confirm these are estimates for my portion", isOn: $confirmed)
                }
                Button(existing == nil ? "Save meal" : "Save correction") {
                    if store.perform({ service in
                        guard let energy = try parseOptionalNumber(calories), let p = try parseOptionalNumber(protein),
                              let c = try parseOptionalNumber(carbs), let f = try parseOptionalNumber(fat) else {
                            throw TrainerError.invalid("Enter each nutrient estimate explicitly, including known zero values.")
                        }
                        var meal = existing ?? Meal(name: name, nutrients: Nutrients())
                        meal.name = name; meal.nutrients = Nutrients(calories: energy, protein: p, carbs: c, fat: f); meal.occurredAt = date
                        try service.saveMeal(meal, asRecipe: saveRecipe)
                    }) { dismiss() }
                }.disabled(!confirmed)
                if let existing {
                    Button("Delete meal", role: .destructive) { confirmDelete = true }
                        .confirmationDialog("Delete this meal estimate?", isPresented: $confirmDelete) {
                            Button("Delete", role: .destructive) {
                                if store.perform({ service in try service.deleteMeal(id: existing.id) }) { dismiss() }
                            }
                        }
                }
            }.navigationTitle(existing == nil ? "New meal" : "Correct meal").toolbar { Button("Cancel") { dismiss() } }
                .onAppear {
                    if let existing {
                        name = existing.name; calories = String(existing.nutrients.calories); protein = String(existing.nutrients.protein)
                        carbs = String(existing.nutrients.carbs); fat = String(existing.nutrients.fat); date = existing.occurredAt
                    }
                }
        }
    }
}
struct RecipePortionView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    let recipe: Recipe
    @State private var servings = 1.0
    var body: some View {
        NavigationStack {
            Form {
                Text(recipe.name).font(.headline)
                Stepper("\(number(servings)) saved portions", value: $servings, in: 0.5...10, step: 0.5)
                Text("\(number(recipe.perServing.calories * servings)) kcal estimated")
                Button("Confirm portion and log") {
                    if store.perform({ service in
                        try service.saveMeal(Meal(name: recipe.name, nutrients: try service.scaleNutrients(recipe.perServing, servings: servings)))
                    }) { dismiss() }
                }
            }.navigationTitle("Reuse a portion").toolbar { Button("Cancel") { dismiss() } }
        }
    }
}
