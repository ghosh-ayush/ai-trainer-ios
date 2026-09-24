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

// MARK: - Diet tab (ADR-016)
// Every number shown here is computed by the Python core from the cited diet policy. Swift only
// displays it, collects what the athlete enters, and sends each change as one state command.

/// Diet tab root: today's targets and what is left, a suggested adjustment, weigh-ins and food ideas.
struct DietTabView: View {
    @EnvironmentObject private var store: AppStore
    @State private var showSetup = false
    @State private var showWeighIn = false
    @State private var showSearch = false
    @State private var selectedFood: FoodChoice?
    @State private var showWeighIns = false
    @StateObject private var health = HealthKitService()
    var body: some View {
        let diet = store.diet
        TabRoot("Diet") {
            switch diet.status {
            case .withheld:
                StitchNotice("Diet targets are withheld", body: diet.message, tone: .warn)
                Button("Review my answers") { showSetup = true }.buttonStyle(.stitch(.secondary))
                weightSection(nil)
            case .needsInput:
                StitchCard("Set up your diet", body: diet.message.isEmpty ? "Answer a few questions to get daily targets." : diet.message)
                Button(store.state.dietProfile == nil ? "Set up diet" : "Review targets") { showSetup = true }.buttonStyle(.stitch())
                if !store.state.weighIns.isEmpty { weightSection(nil) }
            case .ready:
                if let targets = diet.targets { DietTargetsCard(targets: targets, eaten: diet.eaten, remaining: diet.remaining) }
                if let adjustment = diet.adjustment { DietAdjustmentCard(adjustment: adjustment) }
                weightSection(diet.trend)
                foodSection(diet.suggestions)
                mealsSection()
                ForEach(diet.notes, id: \.self) { StitchFootnote($0) }
                NavigationLink { DietEvidenceView(citations: diet.citations, version: diet.policyVersion) } label: {
                    StitchListRow("Why these numbers", subtitle: "\(diet.citations.count) cited values · \(diet.policyVersion)", symbol: "text.book.closed")
                }
                .buttonStyle(.plain)
                Button("Change goal or diet") { showSetup = true }.buttonStyle(.stitch(.secondary))
            }
        }
        .sheet(isPresented: $showSetup) { DietSetupView() }
        .sheet(isPresented: $showWeighIn) { WeighInSheet() }
        .sheet(isPresented: $showWeighIns) { WeighInsSheet() }
        .sheet(isPresented: $showSearch) { FoodSearchView(pattern: store.state.dietProfile?.pattern) }
        .sheet(item: $selectedFood) { FoodPortionSheet(choice: $0) }
    }

    @ViewBuilder private func weightSection(_ trend: WeightTrend?) -> some View {
        StitchSectionLabel("Body weight", meta: store.state.weighIns.count == 1 ? "1 weigh-in" : "\(store.state.weighIns.count) weigh-ins")
        StitchCard {
            if let trend {
                StitchStat("Trend weight", value: DietFormat.mass(trend.latestKg, unit: DietFormat.unit(store)), unit: DietFormat.unit(store).rawValue)
                StitchKeyValue("Change per week", value: "\(DietFormat.signedMass(trend.weeklyChangeKg, unit: DietFormat.unit(store))) \(DietFormat.unit(store).rawValue) · \(trend.weighIns) weigh-ins in \(trend.windowDays) days")
            } else if let latest = store.state.weighIns.max(by: { $0.measuredAt < $1.measuredAt }) {
                StitchStat("Latest weigh-in", value: DietFormat.mass(latest.kg, unit: DietFormat.unit(store)), unit: DietFormat.unit(store).rawValue)
                StitchFootnote("A few more weigh-ins over the coming days let your targets adapt to your trend.")
            } else {
                StitchCardText(title: "No weigh-ins yet", text: "Targets adapt to your weight trend, never to a guess.")
            }
        }
        HStack(spacing: 8) {
            Button("Log weight") { showWeighIn = true }.buttonStyle(.stitch(.secondary, compact: true))
            Button(health.loading ? "Reading…" : "From Apple Health") { importFromHealth() }
                .buttonStyle(.stitch(.secondary, compact: true)).disabled(health.loading || store.isWorking)
        }
        if !store.state.weighIns.isEmpty {
            Button("See or delete weigh-ins") { showWeighIns = true }.buttonStyle(.stitch(.link, compact: true))
        }
    }

    @ViewBuilder private func foodSection(_ suggestions: [FoodSuggestion]) -> some View {
        StitchSectionLabel("Food ideas", meta: "Fit what is left today")
        if suggestions.isEmpty {
            StitchCard("Nothing to suggest", body: "You have reached today's energy target, or no food fits what is left.")
        }
        ForEach(suggestions, id: \.foodID) { suggestion in
            Button { selectedFood = FoodChoice(suggestion: suggestion) } label: {
                StitchListRow(suggestion.name, subtitle: suggestion.reason, symbol: "leaf")
            }
            .buttonStyle(.plain)
        }
        Button("Log food") { showSearch = true }.buttonStyle(.stitch())
    }

    @ViewBuilder private func mealsSection() -> some View {
        let today = store.state.meals.filter { Calendar.current.isDateInToday($0.occurredAt) }.sorted { $0.occurredAt > $1.occurredAt }
        if !today.isEmpty {
            StitchSectionLabel("Eaten today")
            ForEach(today) { meal in
                StitchListRow(meal.name, subtitle: "\(number(meal.nutrients.calories)) kcal · \(number(meal.nutrients.protein)) g protein", symbol: "fork.knife", chevron: false)
                    .contextMenu {
                        Button("Delete", role: .destructive) { store.perform { try $0.deleteMeal(id: meal.id) } }
                    }
            }
        }
    }

    private func importFromHealth() {
        Task {
            do {
                let weighIns = try await health.bodyMassWeighIns()
                if weighIns.isEmpty {
                    store.errorMessage = "No body-weight samples were readable. Health may have none, or read access was not granted (Settings ▸ Health)."
                    return
                }
                store.perform({ try $0.importWeighIns(weighIns) }) { added in
                    if !added { store.errorMessage = "Your Apple Health weigh-ins are already here." }
                }
            } catch { store.errorMessage = error.localizedDescription }
        }
    }
}

/// Daily targets with what was eaten and what is left.
struct DietTargetsCard: View {
    let targets: DietTargets
    let eaten: Nutrients
    let remaining: Nutrients?
    var body: some View {
        StitchSectionLabel("Today's targets", meta: targets.basis == "adjustment" ? "Adjusted to your trend" : "")
        StitchCard(tone: .accent) {
            StitchStat("Energy left", value: number(remaining?.calories ?? Double(targets.energyKcal)), unit: "of \(targets.energyKcal) kcal")
            row("Protein", left: remaining?.protein, target: targets.proteinG)
            row("Carbohydrate", left: remaining?.carbs, target: targets.carbohydrateG)
            row("Fat", left: remaining?.fat, target: targets.fatG)
            StitchKeyValue("Fibre target", value: "\(targets.fibreG) g")
            StitchFootnote("Eaten so far: \(number(eaten.calories)) kcal. Targets are estimates from published equations, not a clinical prescription.")
        }
    }
    private func row(_ label: String, left: Double?, target: Int) -> some View {
        StitchKeyValue(label, value: "\(number(left ?? Double(target))) g left of \(target) g")
    }
}

/// A suggested change to the targets; nothing changes until the athlete accepts it.
struct DietAdjustmentCard: View {
    @EnvironmentObject private var store: AppStore
    let adjustment: DietAdjustment
    var body: some View {
        StitchSectionLabel("Suggested change")
        StitchCard(tone: .accent) {
            StitchCardText(title: adjustment.title, text: adjustment.body)
            HStack(spacing: 8) {
                Button("Accept") { store.perform { try $0.acceptDietAdjustment(expected: adjustment.targets) } }
                    .buttonStyle(.stitch(.primary, compact: true))
                Button("Not now") { store.perform { try $0.rejectDietAdjustment(expected: adjustment.targets) } }
                    .buttonStyle(.stitch(.secondary, compact: true))
            }
        }
    }
}

/// Setup and later changes: body data, activity, goal, diet type, cuisines and the safety questions.
struct DietSetupView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    @State private var options: DietOptions?
    @State private var profile = DietProfile()
    /// Nil until the athlete picks one: the equation's sex is never assumed.
    @State private var sex: EquationSex?
    @State private var heightText = ""
    @State private var birthYearText = ""
    @State private var bodyFatText = ""
    @State private var weightText = ""
    @State private var scoffAnswers: [Bool] = []
    @State private var preview: DietView?
    var body: some View {
        Group {
            if let options {
                form(options)
            } else {
                StitchCard("Loading", body: "Reading the diet policy.")
            }
        }
        .stitchSheet("Your diet") { dismiss() }
        .onAppear(perform: load)
    }

    @ViewBuilder private func form(_ options: DietOptions) -> some View {
        StitchSectionLabel("About you", meta: "Used by the energy equation")
        StitchField("Sex for the equation", value: sex.map { $0 == .female ? "Female" : "Male" } ?? "Choose") {
            Picker("Sex", selection: $sex) {
                Text("Choose").tag(EquationSex?.none)
                Text("Female").tag(EquationSex?.some(.female))
                Text("Male").tag(EquationSex?.some(.male))
            }
            .labelsHidden()
        }
        entry("Birth year", text: $birthYearText, keyboard: .numberPad)
        entry("Height (cm)", text: $heightText, keyboard: .decimalPad)
        if store.state.weighIns.isEmpty {
            entry("Current weight (\(DietFormat.unit(store).rawValue))", text: $weightText, keyboard: .decimalPad)
        }
        entry("Body fat % (optional, only if measured)", text: $bodyFatText, keyboard: .decimalPad)
        choices("Daily activity", options.activityLevels, selected: profile.activity.rawValue) { profile.activity = ActivityLevel(rawValue: $0) ?? profile.activity }
        choices("Goal", options.goals, selected: profile.goal.rawValue) { profile.goal = DietGoal(rawValue: $0) ?? profile.goal }
        if profile.goal == .endurance {
            choices("Training load", options.trainingLoads, selected: profile.trainingLoad?.rawValue ?? "") { profile.trainingLoad = TrainingLoad(rawValue: $0) }
        }
        choices("Diet type", options.patterns, selected: profile.pattern.rawValue) { profile.pattern = DietPattern(rawValue: $0) ?? profile.pattern }
        choices(options.paceQuestion, options.paces, selected: (profile.pace ?? options.defaultPace).rawValue) {
            profile.pace = AdaptationPace(rawValue: $0)
        }
        StitchFootnote(options.paceNote)
        StitchSectionLabel("Cuisines you enjoy", meta: "Ranks food ideas")
        ForEach(options.cuisines) { cuisine in
            StitchToggleField(cuisine.title, isOn: Binding(
                get: { profile.cuisines.contains(cuisine.id) },
                set: { on in profile.cuisines = on ? profile.cuisines + [cuisine.id] : profile.cuisines.filter { $0 != cuisine.id } }),
                on: "Yes", off: "No")
        }
        StitchSectionLabel("Safety questions", meta: "Private, stored on this device")
        StitchToggleField("Pregnant", isOn: $profile.screening.pregnant, on: "Yes", off: "No")
        StitchToggleField("Breastfeeding", isOn: $profile.screening.lactating, on: "Yes", off: "No")
        ForEach(options.exclusions) { exclusion in
            StitchToggleField(exclusion.title, isOn: Binding(
                get: { profile.screening.conditions.contains(exclusion.id) },
                set: { on in profile.screening.conditions = on ? profile.screening.conditions + [exclusion.id] : profile.screening.conditions.filter { $0 != exclusion.id } }),
                on: "Yes", off: "No")
            StitchFootnote(exclusion.detail)
        }
        StitchFootnote("Eating and food questions (SCOFF). Answer honestly; the app never shares them.")
        ForEach(Array(options.scoffQuestions.enumerated()), id: \.offset) { index, question in
            StitchToggleField(question, isOn: Binding(
                get: { index < scoffAnswers.count && scoffAnswers[index] },
                set: { on in if index < scoffAnswers.count { scoffAnswers[index] = on } }),
                on: "Yes", off: "No")
        }
        Button("Preview targets") { previewTargets() }.buttonStyle(.stitch(.secondary)).disabled(!complete)
        if !complete {
            StitchFootnote("Enter your sex for the equation, birth year, height\(store.state.weighIns.isEmpty ? " and weight" : "") to preview. Nothing is assumed.")
        }
        if let preview { previewSection(preview) }
    }

    @ViewBuilder private func previewSection(_ preview: DietView) -> some View {
        switch preview.status {
        case .ready:
            if let targets = preview.targets {
                StitchCard(tone: .accent) {
                    StitchStat("Daily energy", value: "\(targets.energyKcal)", unit: "kcal")
                    StitchKeyValue("Protein · carbohydrate · fat", value: "\(targets.proteinG) · \(targets.carbohydrateG) · \(targets.fatG) g")
                    StitchKeyValue("Fibre", value: "\(targets.fibreG) g")
                    ForEach(preview.notes, id: \.self) { StitchFootnote($0) }
                }
                Button("Use these targets") {
                    store.perform({ try $0.setDietTargets(profile: currentProfile(), expected: targets) }) { _ in dismiss() }
                }
                .buttonStyle(.stitch())
            }
        case .withheld:
            StitchNotice("Targets withheld", body: preview.message, tone: .warn)
            Button("Save my answers") {
                store.perform({ try $0.saveDietProfile(currentProfile()) }) { _ in dismiss() }
            }
            .buttonStyle(.stitch())
            StitchFootnote("Saving keeps your answers so the app stops showing targets that no longer fit.")
        case .needsInput:
            StitchNotice("More needed", body: preview.message, tone: .warn)
        }
    }

    /// Everything the equations need has been entered; nothing is defaulted.
    private var complete: Bool {
        sex != nil && Int(birthYearText) != nil && Double(heightText.replacingOccurrences(of: ",", with: ".")) != nil
            && (!store.state.weighIns.isEmpty || Double(weightText.replacingOccurrences(of: ",", with: ".")) != nil)
    }

    private func entry(_ label: String, text: Binding<String>, keyboard: UIKeyboardType) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).stitch(.monoLabel).textCase(.uppercase).foregroundStyle(Stitch.textMuted)
            TextField(label, text: text).keyboardType(keyboard).stitch(.monoBody).foregroundStyle(Stitch.textPrimary)
        }
        .padding(.horizontal, 16).padding(.vertical, 14).glass(radius: 8)
    }

    @ViewBuilder private func choices(_ label: String, _ items: [ChoiceOption], selected: String, choose: @escaping (String) -> Void) -> some View {
        StitchSectionLabel(label)
        ForEach(items) { item in
            Button { choose(item.id) } label: {
                StitchListRow(item.title, subtitle: item.detail, symbol: item.id == selected ? "checkmark.circle.fill" : "circle", chevron: false)
            }
            .buttonStyle(.plain)
        }
    }

    private func load() {
        if let saved = store.state.dietProfile {
            profile = saved
            sex = saved.sex
            heightText = number(saved.heightCm)
            birthYearText = String(saved.birthYear)
            bodyFatText = saved.bodyFatPercent.map(number) ?? ""
        }
        store.read({ try $0.dietOptions() }) { loaded in
            options = loaded
            let saved = profile.screening.scoffAnswers
            scoffAnswers = saved.count == loaded.scoffQuestions.count ? saved : Array(repeating: false, count: loaded.scoffQuestions.count)
        }
    }

    /// The profile as entered; malformed numbers are left for the core to refuse.
    private func currentProfile() -> DietProfile {
        var entered = profile
        if let sex { entered.sex = sex }
        entered.heightCm = Double(heightText.replacingOccurrences(of: ",", with: ".")) ?? 0
        entered.birthYear = Int(birthYearText) ?? 0
        entered.bodyFatPercent = bodyFatText.isEmpty ? nil : Double(bodyFatText.replacingOccurrences(of: ",", with: "."))
        entered.screening.scoffAnswers = scoffAnswers
        if entered.goal != .endurance { entered.trainingLoad = nil }
        return entered
    }

    private func previewTargets() {
        let entered = currentProfile()
        let typedWeight = Double(weightText.replacingOccurrences(of: ",", with: "."))
        let unit = DietFormat.unit(store)
        store.perform({ service -> DietView in
            if service.repository.snapshot.weighIns.isEmpty, let typedWeight {
                let now = Date()
                try service.logWeighIn(WeighIn(kg: DietFormat.kilograms(typedWeight, from: unit), measuredAt: now,
                                               utcOffsetSeconds: TimeZone.current.secondsFromGMT(for: now)))
            }
            return try service.dietPreview(profile: entered)
        }) { preview = $0 }
    }
}

/// Log one body-weight measurement.
struct WeighInSheet: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    @State private var text = ""
    @State private var date = Date()
    var body: some View {
        let unit = DietFormat.unit(store)
        Group {
            VStack(alignment: .leading, spacing: 4) {
                Text("Weight (\(unit.rawValue))").stitch(.monoLabel).textCase(.uppercase).foregroundStyle(Stitch.textMuted)
                TextField("Weight", text: $text).keyboardType(.decimalPad).stitch(.monoBody).foregroundStyle(Stitch.textPrimary)
            }
            .padding(.horizontal, 16).padding(.vertical, 14).glass(radius: 8)
            StitchField("Measured at", value: date.formatted(date: .abbreviated, time: .shortened)) {
                DatePicker("Measured at", selection: $date, in: ...Date()).labelsHidden()
            }
            StitchFootnote("Weigh at a similar time each day, for example after waking. Day-to-day changes are mostly water.")
            Button("Save weigh-in") {
                guard let value = Double(text.replacingOccurrences(of: ",", with: ".")) else {
                    store.errorMessage = "Enter your weight as a number."
                    return
                }
                let weighIn = WeighIn(kg: DietFormat.kilograms(value, from: unit), measuredAt: date,
                                      utcOffsetSeconds: TimeZone.current.secondsFromGMT(for: date))
                store.perform({ try $0.logWeighIn(weighIn) }) { _ in dismiss() }
            }
            .buttonStyle(.stitch())
        }
        .stitchSheet("Log weight") { dismiss() }
    }
}

/// Every weigh-in, newest first, with delete: a mistyped reading must never lock the Diet tab.
struct WeighInsSheet: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        let unit = DietFormat.unit(store)
        Group {
            StitchFootnote("Only the first weigh-in of each day counts toward your trend. Deleting an Apple Health reading here keeps it out of later imports; it stays in Health.")
            ForEach(store.state.weighIns.sorted { $0.measuredAt > $1.measuredAt }) { weighIn in
                HStack {
                    StitchListRow("\(DietFormat.mass(weighIn.kg, unit: unit)) \(unit.rawValue)",
                                  subtitle: "\(weighIn.measuredAt.formatted(date: .abbreviated, time: .shortened)) · \(weighIn.source == "appleHealth" ? "Apple Health" : "typed")",
                                  symbol: "scalemass", chevron: false)
                    Button(role: .destructive) { store.perform { try $0.deleteWeighIn(id: weighIn.id) } } label: {
                        Image(systemName: "trash")
                    }
                    .buttonStyle(.stitch(.destructive, compact: true))
                }
            }
        }
        .stitchSheet("Weigh-ins") { dismiss() }
    }
}

/// A food to log: from a suggestion or a search result.
struct FoodChoice: Identifiable {
    let id: Int
    let name: String
    let portions: [FoodPortion]
    let per100g: Nutrients
    init(suggestion: FoodSuggestion) {
        id = suggestion.foodID; name = suggestion.name; portions = [suggestion.portion]
        let factor = suggestion.portion.grams > 0 ? 100 / suggestion.portion.grams : 0
        per100g = Nutrients(calories: suggestion.nutrients.calories * factor, protein: suggestion.nutrients.protein * factor,
                            carbs: suggestion.nutrients.carbs * factor, fat: suggestion.nutrients.fat * factor)
    }
    init(item: FoodItem) { id = item.id; name = item.name; portions = item.portions; per100g = item.per100g }
}

/// Search the bundled USDA foods.
struct FoodSearchView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    let pattern: DietPattern?
    @State private var query = ""
    @State private var results: [FoodItem] = []
    @State private var selected: FoodChoice?
    var body: some View {
        Group {
            VStack(alignment: .leading, spacing: 4) {
                Text("Search foods").stitch(.monoLabel).textCase(.uppercase).foregroundStyle(Stitch.textMuted)
                TextField("e.g. lentils, greek yogurt, chicken breast", text: $query)
                    .stitch(.monoBody).foregroundStyle(Stitch.textPrimary)
                    .onSubmit(search).submitLabel(.search)
            }
            .padding(.horizontal, 16).padding(.vertical, 14).glass(radius: 8)
            Button("Search") { search() }.buttonStyle(.stitch(.secondary, compact: true))
            ForEach(results) { item in
                Button { selected = FoodChoice(item: item) } label: {
                    StitchListRow(item.name, subtitle: "\(number(item.per100g.calories)) kcal · \(number(item.per100g.protein)) g protein per 100 g", symbol: "magnifyingglass")
                }
                .buttonStyle(.plain)
            }
            StitchFootnote("Food composition: USDA FoodData Central (public domain).")
        }
        .stitchSheet("Log food") { dismiss() }
        .sheet(item: $selected) { FoodPortionSheet(choice: $0) { dismiss() } }
    }
    private func search() {
        let text = query
        store.read({ try $0.searchFoods(text, pattern: pattern) }) { results = $0 }
    }
}

/// Choose how much of a food was eaten; the core stores the USDA nutrients for that amount.
struct FoodPortionSheet: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    let choice: FoodChoice
    var onLogged: () -> Void = {}
    @State private var portionIndex = 0
    @State private var count = 1.0
    var body: some View {
        let portion = choice.portions.indices.contains(portionIndex) ? choice.portions[portionIndex] : FoodPortion(label: "100 g", grams: 100)
        let grams = portion.grams * count
        Group {
            StitchSectionLabel(choice.name)
            ForEach(Array(choice.portions.enumerated()), id: \.offset) { index, option in
                Button { portionIndex = index } label: {
                    StitchListRow(option.label, subtitle: "\(number(option.grams)) g", symbol: index == portionIndex ? "checkmark.circle.fill" : "circle", chevron: false)
                }
                .buttonStyle(.plain)
            }
            StitchField("Portions", value: number(count)) {
                StitchStepperButtons(decrement: { count = max(0.25, count - 0.25) }, increment: { count = min(20, count + 0.25) })
            }
            StitchCard {
                StitchStat("About", value: number(choice.per100g.calories * grams / 100), unit: "kcal in \(number(grams)) g")
                StitchKeyValue("Protein · carbs · fat", value: "\(number(choice.per100g.protein * grams / 100)) · \(number(choice.per100g.carbs * grams / 100)) · \(number(choice.per100g.fat * grams / 100)) g")
            }
            Button("Log \(number(grams)) g") {
                store.perform({ try $0.saveFoodMeal(foodID: choice.id, grams: grams) }) { _ in
                    dismiss()
                    onLogged()
                }
            }
            .buttonStyle(.stitch())
        }
        .stitchSheet("How much?") { dismiss() }
    }
}

/// Every diet value with the research behind it.
struct DietEvidenceView: View {
    let citations: [DietCitation]
    let version: String
    var body: some View {
        DetailScreen("Why these numbers") {
            StitchNotice("Evidence-based, not clinician-reviewed", body: "Each value comes from a published study or an official reference (\(version)). Targets are estimates for healthy adults.")
            ForEach(Array(citations.enumerated()), id: \.offset) { _, citation in
                StitchCard {
                    StitchKeyValue(citation.parameter, value: citation.value)
                    Text(citation.citation).stitch(.body13).foregroundStyle(Stitch.textSecondary)
                    StitchFootnote([citation.locator, citation.certainty].filter { !$0.isEmpty }.joined(separator: " · "))
                }
            }
        }
    }
}

/// Display units for body mass: the athlete's training unit. Conversion is display only;
/// weigh-ins are stored in kilograms.
enum DietFormat {
    static let kilogramsPerPound = 0.45359237
    @MainActor static func unit(_ store: AppStore) -> MassUnit { store.state.profile?.preferredUnit ?? .kg }
    static func kilograms(_ value: Double, from unit: MassUnit) -> Double { unit == .lb ? value * kilogramsPerPound : value }
    static func mass(_ kg: Double, unit: MassUnit) -> String { number(((unit == .lb ? kg / kilogramsPerPound : kg) * 10).rounded() / 10) }
    static func signedMass(_ kg: Double, unit: MassUnit) -> String {
        let value = unit == .lb ? kg / kilogramsPerPound : kg
        return (value >= 0 ? "+" : "−") + number((abs(value) * 100).rounded() / 100)
    }
}
