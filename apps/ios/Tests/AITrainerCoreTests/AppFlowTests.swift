import XCTest
@testable import AITrainerCore

/// End-to-end flows through `TrainerService` with the real embedded core: what the app does,
/// how state is saved, reloaded and migrated. Individual rules are covered in Python.
final class AppFlowTests: XCTestCase {
    let now = Date(timeIntervalSinceReferenceDate: 811_382_400)
    let core = LocalPythonTrainerService(transport: EmbeddedPythonTransport())

    func service(storage: MemoryPersistence = MemoryPersistence()) throws -> TrainerService {
        TrainerService(repository: try StateRepository(persistence: storage, core: core),
                       library: try core.library(permitsFixtures: true), core: core)
    }
    /// Accepts the fixture plan, confirms 100 lb with a 105 step, and logs two 3 x 10 @ RIR 2 sessions.
    func trainedService(storage: MemoryPersistence = MemoryPersistence()) throws -> TrainerService {
        let service = try service(storage: storage)
        var profile = Profile()
        profile.adultConfirmed = true; profile.supportedScopeConfirmed = true
        profile.equipment = ["barbell", "dumbbell", "machine"]; profile.preferredExercises = ["bench"]
        try service.acceptInitialPlan(profile: profile, now: now)
        let slot = try XCTUnwrap(service.repository.snapshot.nextPlan?.slots.first)
        try service.configureLoad(slotID: slot.id, load: 100, options: [100, 105])
        for daysAgo in [5.0, 2.0] {
            let date = now.addingTimeInterval(-daysAgo * 86400)
            try service.start(now: date)
            let session = try XCTUnwrap(service.repository.snapshot.activeSession)
            for index in 0..<3 {
                try service.saveSet(sessionID: session.id, slotID: slot.id, index: index, load: 100, reps: 10, rir: 2, now: date)
            }
            try service.finish(now: date.addingTimeInterval(1800))
        }
        return service
    }

    func testProgressionIsProposedThenAppliedOnlyOnAcceptance() throws {
        let service = try trainedService()
        let slot = try XCTUnwrap(service.repository.snapshot.nextPlan?.slots.first)
        let decision = try service.request(.progression(slot.id), now: now)
        XCTAssertEqual(decision.reason, "QUALIFYING_EXPOSURES_COMPLETE")
        XCTAssertEqual(service.repository.snapshot.nextPlan?.slots.first?.load, 100)
        let recommendation = try XCTUnwrap(service.repository.snapshot.recommendations.last)
        XCTAssertEqual(recommendation.request, .progression(slot.id))
        try service.acceptRecommendation(id: recommendation.id, now: now)
        XCTAssertEqual(service.repository.snapshot.nextPlan?.slots.first?.load, 105)
    }
    func testSetsCarryTheSlotContextAndUnknownsStayNil() throws {
        let service = try trainedService()
        let log = try XCTUnwrap(service.repository.snapshot.sessions.first?.logs.first)
        XCTAssertEqual(log.unit, .lb)
        XCTAssertEqual(log.basis, .total)
        try service.start(now: now)
        let session = try XCTUnwrap(service.repository.snapshot.activeSession)
        try service.saveSet(sessionID: session.id, slotID: session.plan.slots[0].id, index: 0, load: nil, reps: 0, rir: nil, now: now)
        let saved = try XCTUnwrap(service.repository.snapshot.activeSession?.logs.first)
        XCTAssertNil(saved.load)
        XCTAssertNil(saved.rir)
        XCTAssertEqual(service.repository.snapshot.activeSession?.restEndsAt, now.addingTimeInterval(120))
    }
    func testDomainErrorsArriveAsTypedSwiftErrors() throws {
        let service = try trainedService()
        XCTAssertThrowsError(try service.acceptRecommendation(id: UUID())) { XCTAssertEqual($0 as? TrainerError, .notFound) }
    }
    func testNoProposalAnswerDoesNotRewriteTheFile() throws {
        let storage = MemoryPersistence()
        let service = try trainedService(storage: storage)
        let saved = storage.data, revision = service.repository.snapshot.revision
        let decision = try service.request(.shorten(300), now: now)
        XCTAssertEqual(decision.reason, "ALREADY_FITS")
        XCTAssertEqual(storage.data, saved)
        XCTAssertEqual(service.repository.snapshot.revision, revision)
    }
    func testTransportFailureCannotPublishOrSaveCandidate() throws {
        struct Offline: TrainerCoreTransport {
            func exchange(_ request: Data) throws -> Data { throw TrainerError.unsupported }
        }
        let storage = MemoryPersistence()
        let repository = try StateRepository(persistence: storage, core: core)
        let before = repository.snapshot
        let offline = TrainerService(repository: repository, library: try core.library(permitsFixtures: true),
                                     core: LocalPythonTrainerService(transport: Offline()))
        XCTAssertThrowsError(try offline.request(.shorten(30)))
        XCTAssertEqual(repository.snapshot, before)
        XCTAssertNil(storage.data)
    }
    func testFailedSaveDoesNotPublishCandidateState() throws {
        let storage = MemoryPersistence()
        let service = try trainedService(storage: storage)
        let slot = try XCTUnwrap(service.repository.snapshot.nextPlan?.slots.first)
        try service.request(.progression(slot.id), now: now)
        let before = service.repository.snapshot
        storage.failWrites = true
        XCTAssertThrowsError(try service.acceptRecommendation(id: before.recommendations[0].id, now: now))
        XCTAssertEqual(service.repository.snapshot, before)
    }
    func testActiveSessionSurvivesReload() throws {
        let storage = MemoryPersistence()
        let service = try trainedService(storage: storage)
        try service.start(now: now)
        try service.setPaused(true)
        let restored = try StateRepository(persistence: storage, core: core)
        XCTAssertEqual(restored.snapshot, service.repository.snapshot)
        XCTAssertEqual(restored.snapshot.activeSession?.status, .paused)
    }
    func testSubsecondDatesSurviveTheCoreRoundTripExactly() throws {
        let service = try trainedService()
        var checkIn = CheckIn(); checkIn.occurredAt = Date(timeIntervalSinceReferenceDate: 811_382_400.1234567)
        try service.start(checkIn: checkIn, now: now)
        XCTAssertEqual(service.repository.snapshot.activeSession?.checkIn.occurredAt, checkIn.occurredAt)
    }
    func testVersionOneFileIsMigratedByTheCore() throws {
        let storage = MemoryPersistence()
        let service = try trainedService(storage: storage)
        let slot = try XCTUnwrap(service.repository.snapshot.nextPlan?.slots.first)
        try service.request(.progression(slot.id), now: now)
        // Rewrite the saved file into the v1 shape the previous app version wrote.
        var object = try XCTUnwrap(JSONSerialization.jsonObject(with: XCTUnwrap(storage.data)) as? [String: Any])
        var recommendations = try XCTUnwrap(object["recommendations"] as? [[String: Any]])
        recommendations[0]["request"] = ["progression": ["_0": slot.id.uuidString]]
        object["recommendations"] = recommendations
        object["schemaVersion"] = 1
        object["weighIns"] = nil
        object["dietDecisions"] = nil
        storage.data = try JSONSerialization.data(withJSONObject: object)
        let migrated = try StateRepository(persistence: storage, core: core).snapshot
        XCTAssertEqual(migrated.schemaVersion, 3)
        XCTAssertEqual(migrated.weighIns, [])
        XCTAssertEqual(migrated.recommendations.first?.request, .progression(slot.id))
    }
    func testCorruptStoreIsNotOverwritten() {
        let data = Data("bad-json".utf8), storage = MemoryPersistence(data: data)
        XCTAssertThrowsError(try StateRepository(persistence: storage, core: core)) { XCTAssertEqual($0 as? TrainerError, .corruptStore) }
        XCTAssertEqual(storage.data, data)
    }
    func testDeleteAllClearsEverything() throws {
        let service = try trainedService()
        try service.repository.deleteAll()
        XCTAssertNil(service.repository.snapshot.profile)
        XCTAssertTrue(service.repository.snapshot.sessions.isEmpty)
    }
    func testTodayAutoRequestsAProposalThenShowsIt() throws {
        let service = try trainedService()
        let slot = try XCTUnwrap(service.repository.snapshot.nextPlan?.slots.first)
        XCTAssertEqual(try service.views(now: now).today.autoRequest, slot.id)
        try service.request(.progression(slot.id), now: now)
        let views = try service.views(now: now)
        XCTAssertNil(views.today.autoRequest)
        XCTAssertEqual(views.today.proposals.first?.title, "Proposed · 100 → 105 lb")
        XCTAssertEqual(views.progress.first?.entries.count, 2)
        XCTAssertEqual(try service.loadSteps(base: 100, step: 5).count, 21)
    }
    func testProductionLibraryCannotActivateFixtureContent() throws {
        let production = TrainerService(repository: try StateRepository(persistence: MemoryPersistence(), core: core),
                                        library: try core.library(permitsFixtures: false), core: core)
        var profile = Profile(); profile.adultConfirmed = true; profile.supportedScopeConfirmed = true
        XCTAssertThrowsError(try production.previewInitialPlan(profile: profile, now: now)) { XCTAssertEqual($0 as? TrainerError, .unsupported) }
    }
    func testNutritionScalingAndDailyTotals() throws {
        let service = try service()
        let nutrients = try service.scaleNutrients(Nutrients(calories: 200, protein: 10, carbs: 20, fat: 9), servings: 1.5)
        XCTAssertEqual(nutrients.calories, 300)
        XCTAssertEqual(Meal.total([Meal(name: "Fixture", nutrients: nutrients, occurredAt: now)], on: now).protein, 15)
        XCTAssertThrowsError(try service.scaleNutrients(nutrients, servings: -1))
    }
    func testDietTargetsFlowThroughTheCore() throws {
        let service = try trainedService()
        var profile = DietProfile()
        profile.sex = .male; profile.birthYear = 1996; profile.heightCm = 180; profile.goal = .fatLoss
        profile.screening.scoffAnswers = Array(repeating: false, count: try service.dietOptions(now: now).scoffQuestions.count)
        XCTAssertEqual(try service.dietPreview(profile: profile, now: now).status, .needsInput)
        try service.logWeighIn(WeighIn(kg: 80, measuredAt: now.addingTimeInterval(-3600)), now: now)
        let preview = try service.dietPreview(profile: profile, now: now)
        let targets = try XCTUnwrap(preview.targets)
        XCTAssertFalse(preview.citations.isEmpty)
        var stale = targets; stale.energyKcal += 10
        XCTAssertThrowsError(try service.setDietTargets(profile: profile, expected: stale, now: now)) {
            XCTAssertEqual($0 as? TrainerError, .staleProposal)
        }
        try service.setDietTargets(profile: profile, expected: targets, now: now)
        let lentils = try XCTUnwrap(service.searchFoods("lentils", pattern: .vegan).first)
        try service.saveFoodMeal(foodID: lentils.id, grams: 200, occurredAt: now)
        let diet = try service.views(now: now).diet
        XCTAssertEqual(diet.status, .ready)
        XCTAssertEqual(try XCTUnwrap(diet.remaining).calories, Double(targets.energyKcal) - lentils.per100g.calories * 2, accuracy: 0.2)
    }
    func testBundledResourcesLoad() throws {
        let catalog = try ExerciseCatalog.bundled()
        XCTAssertEqual(catalog.exercises.count, 876)
        let annotated = catalog.exercises.filter { !($0.evidence ?? []).isEmpty }
        XCTAssertFalse(annotated.isEmpty, "research annotations decode from the bundled catalog")
        XCTAssertTrue(annotated.allSatisfy { $0.evidence!.allSatisfy { $0.doi != nil || $0.pmid != nil } })
        XCTAssertTrue(try ThirdPartyNotices.text().contains("Copyright (c) 2026 Nazar Kozak"))
        XCTAssertTrue(try ThirdPartyNotices.text().contains("SIL OPEN FONT LICENSE"))
    }
}
