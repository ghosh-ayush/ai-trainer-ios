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
    /// ADR-018: a replan request (kind only, no fields) crosses the contract. The pinned fixture has no
    /// weekly planner, so the core says so and nothing is stored.
    func testReplanRequestIsUnderstoodAndNeedsAWeeklyPlanner() throws {
        let service = try trainedService()
        let decision = try service.request(.replan(utcOffset: 0), now: now)
        XCTAssertEqual(decision.reason, "REPLAN_UNAVAILABLE")
        XCTAssertNil(decision.week)
        XCTAssertTrue(service.repository.snapshot.recommendations.allSatisfy { $0.request.kind != "replan" })
    }
    /// The model's draft stands in for `OnDeviceSetReader`: an RIR the athlete never said is dropped,
    /// and nothing is recorded until the preview is saved as a normal set.
    func testWordsBecomeAPreviewThatSavesOnlyWhenConfirmed() throws {
        let service = try trainedService()
        try service.start(now: now)
        let before = service.repository.snapshot
        let reading = try service.readSet(text: "bench 100 for 8", draft: SpokenSet(reps: 8, load: 100, rir: 2))
        XCTAssertEqual(service.repository.snapshot, before)
        XCTAssertEqual(reading.ignored, ["rir"])
        let preview = try XCTUnwrap(reading.preview)
        XCTAssertEqual(preview.reps, 8)
        XCTAssertEqual(preview.load, 100)
        XCTAssertNil(preview.rir)
        try service.saveSet(sessionID: preview.sessionID, slotID: preview.slotID, index: preview.index, kind: preview.kind,
                            load: preview.load, reps: preview.reps, rir: preview.rir, now: now)
        let saved = try XCTUnwrap(service.repository.snapshot.activeSession?.logs.first)
        XCTAssertEqual(saved.reps, 8)
        XCTAssertNil(saved.rir)
    }
    /// The real on-device model through the real core. Skipped where Apple's model cannot run (CI);
    /// runs on a Mac with Apple Intelligence on. Whatever the model returns, a kept number was said.
    func testOnDeviceModelDraftsAreGroundedInTheAthletesWords() async throws {
        try XCTSkipUnless(OnDeviceSetReader.isAvailable, "Apple's on-device model is not available here.")
        let service = try trainedService()
        try service.start(now: now)
        let session = try XCTUnwrap(service.repository.snapshot.activeSession)
        let names = session.plan.slots.map { service.library.exercise($0.exerciseID)?.name ?? $0.exerciseID }
        let said: [String: [Double]] = [
            "did 10 reps": [10],
            "bench 100 for 8, one left in the tank": [100, 8, 1],
            "felt heavy, maybe 6": [6],
        ]
        for (text, numbers) in said {
            let draft = try await OnDeviceSetReader.draft(from: text, exerciseNames: names)
            let reading = try service.readSet(text: text, draft: draft)
            let kept = [reading.preview.map { Double($0.reps) }, reading.preview?.load, reading.preview?.rir.map(Double.init)]
            for value in kept.compactMap({ $0 }) {
                XCTAssertTrue(numbers.contains(value), "\(text): kept \(value), which was never said")
            }
        }
    }
    /// ADR-023: a chat answer comes from the core, keeps only what the athlete said, offers the
    /// proposal as an action and changes nothing by itself.
    func testChatAnswersFromRecordsAndChangesNothing() throws {
        let service = try trainedService()
        let before = service.repository.snapshot
        let names = service.chatExerciseNames
        XCTAssertEqual(names.first, "Barbell bench press")  // the next session's exercises come first
        XCTAssertEqual(Set(names).count, names.count)
        let draft = ChatDraft(topic: .exerciseProgress, exercise: "Barbell bench press", minutes: 15)
        let reply = try service.chat(text: "why is my bench not going up?", draft: draft, now: now)
        XCTAssertEqual(reply.ignored, ["minutes"])
        XCTAssertEqual(reply.reading, "How Barbell bench press is going")
        XCTAssertEqual(reply.lines.first, "Good news: Barbell bench press is ready to move up.")
        XCTAssertTrue(reply.lines.dropFirst().first?.hasPrefix("Last time: ") ?? false)
        let slot = try XCTUnwrap(before.nextPlan?.slots.first)
        XCTAssertEqual(reply.actions.first { $0.kind == .requestProgression }?.slotID, slot.id)
        XCTAssertEqual(service.repository.snapshot, before)
    }
    /// The real on-device chat reader through the real core. Skipped where Apple's model cannot run
    /// (CI). Whatever the model returns: pain is answered as pain, and a kept number was said.
    func testOnDeviceChatReadingIsGroundedInTheAthletesWords() async throws {
        try XCTSkipUnless(OnDeviceChatReader.isAvailable, "Apple's on-device model is not available here.")
        let service = try trainedService()
        let names = service.chatExerciseNames
        let pain = try await OnDeviceChatReader.draft(from: "I'm sick and my knee hurts", exerciseNames: names)
        XCTAssertEqual(try service.chat(text: "I'm sick and my knee hurts", draft: pain, now: now).topic, .pain)
        for (text, said) in [("I only have 20 minutes today", 20), ("why is my bench not going up?", nil)] as [(String, Int?)] {
            let draft = try await OnDeviceChatReader.draft(from: text, exerciseNames: names)
            let reply = try service.chat(text: text, draft: draft, now: now)
            if let minutes = draft.minutes, minutes != said {
                XCTAssertTrue(reply.ignored.contains("minutes"), "\(text): kept \(minutes) minutes, which was never said")
            }
        }
    }
    /// Movement roles read in the bundle's words. The pinned fixture has no weekly planner, so it
    /// names no roles and each reads as it is; an unknown exercise has no role at all.
    func testRoleNamesComeFromTheContentBundle() throws {
        let library = try service().library
        let exercise = try XCTUnwrap(library.exercises.first)
        XCTAssertEqual(library.roleNames, [:])
        XCTAssertEqual(library.roleName(of: exercise.id), exercise.role)
        XCTAssertNil(library.roleName(of: "no-such-exercise"))
    }
    /// ADR-027: the real on-device writer rewords a real answer, and the core decides whether it may be
    /// shown. Skipped where Apple's model cannot run (CI). Pain answers are never reworded.
    func testOnDeviceWordingIsShownOnlyWhenTheCoreAcceptsIt() async throws {
        try XCTSkipUnless(OnDeviceChatReader.isAvailable, "Apple's on-device model is not available here.")
        let service = try trainedService()
        let message = "why is my bench not going up?"
        let reply = try service.chat(text: message, draft: ChatDraft(topic: .exerciseProgress, exercise: "Barbell bench press"), now: now)
        let wording = try await OnDeviceChatWriter.reply(to: message, facts: reply)
        let checked = try service.checkChatWording(reply: reply, wording: wording, message: message)
        if checked.accepted {
            XCTAssertEqual(checked.text, wording.trimmingCharacters(in: .whitespacesAndNewlines))
        } else {
            XCTAssertFalse(checked.dropped.isEmpty, "a refusal says what was not grounded")
        }
        var pain = reply
        pain.topic = .pain
        XCTAssertFalse(try service.checkChatWording(reply: pain, wording: wording, message: message).accepted)
    }
    /// ADR-019: a break pauses automatic proposals; "I'm back" resumes them.
    func testABreakPausesAutomaticProposalsUntilImBack() throws {
        let service = try trainedService()
        try service.setStatus(.onBreak, endsAt: now.addingTimeInterval(7 * 86_400), now: now)
        let paused = try service.views(now: now.addingTimeInterval(60))
        XCTAssertEqual(paused.today.status?.kind, .onBreak)
        XCTAssertNil(paused.today.autoRequest)
        try service.endStatus(now: now.addingTimeInterval(120))
        XCTAssertNil(try service.views(now: now.addingTimeInterval(180)).today.status)
    }
    /// ADR-020: the pinned fixture has no weekly planner, so there are no rings rather than wrong ones,
    /// even though the host sends its UTC offset.
    func testRingsNeedAWeeklyPlanner() throws {
        let service = try trainedService()
        XCTAssertNil(try service.views(now: now).rings)
    }
    /// ADR-021: plates per side come from the core, largest first, and say when a load can't be made.
    func testPlatesPerSideFromTheAthletesOwnPlates() throws {
        let service = try trainedService()
        let exact = try service.plates(load: 102.5, bar: 20, plates: [25, 20, 15, 10, 5, 2.5, 1.25])
        XCTAssertEqual(exact.perSide, [25, 15, 1.25])
        XCTAssertTrue(exact.exact)
        let closest = try service.plates(load: 101, bar: 20, plates: [25, 20, 15, 10, 5, 2.5, 1.25])
        XCTAssertEqual(closest.total, 100)
        XCTAssertFalse(closest.exact)
    }
    /// ADR-022: the spoken coach's words come from the core, built from the plan and logged sets.
    func testSpokenCuesDescribeTheSetJustLoggedAndTheNextOne() throws {
        let service = try trainedService()
        XCTAssertNil(try service.workoutCues(now: now).next)  // no workout, nothing to say
        try service.start(now: now)
        let session = try XCTUnwrap(service.repository.snapshot.activeSession)
        try service.saveSet(sessionID: session.id, slotID: session.plan.slots[0].id, index: 0, load: 100, reps: 8, rir: nil, now: now)
        let cues = try service.workoutCues(now: now.addingTimeInterval(30))
        XCTAssertTrue(cues.afterSet?.hasPrefix("Set 1 of") ?? false, cues.afterSet ?? "none")
        XCTAssertTrue(cues.restOver?.hasPrefix("Rest's over.") ?? false)
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
        XCTAssertEqual(migrated.schemaVersion, 5)
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
