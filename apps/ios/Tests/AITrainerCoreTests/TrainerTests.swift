import XCTest
@testable import AITrainerCore

final class TrainerTests: XCTestCase {
    let now = Date(timeIntervalSince1970: 1_789_689_600)
    let library = ContentLibrary(permitsFixtures: true)
    /// One embedded core per test case, composed the same way `AppStore` does it.
    let core = LocalPythonTrainerService(transport: EmbeddedPythonTransport())
    func fixture() -> AthleteState {
        var state = AthleteState(); var profile = Profile()
        profile.adultConfirmed = true; profile.supportedScopeConfirmed = true
        profile.equipment = ["barbell", "dumbbell", "machine"]; profile.minutes = 60
        state.profile = profile
        let equipment = EquipmentContext(id: "rack-1", name: "Rack 1", kind: "barbell", unit: .lb, basis: .total, availableLoads: [100, 105, 110])
        let slot = Prescription.developmentFixture(exerciseID: "bench", equipment: equipment, load: 100)
        state.program = Program(templateID: "FULL_BODY_FIXTURE_01", libraryVersion: "fixture-1", plans: [SessionPlan(name: "Fixture", slots: [slot])], acceptedAt: now)
        return state
    }
    func exposure(_ state: AthleteState, daysAgo: Int, reps: [Int] = [10, 10, 10], rir: Int? = 2) -> WorkoutSession {
        let date = now.addingTimeInterval(-Double(daysAgo) * 86400)
        var session = WorkoutSession(program: state.program!, plan: state.nextPlan!, checkIn: CheckIn(), now: date, timeZone: "UTC")
        let slot = session.plan.slots[0]
        session.logs = reps.enumerated().map { SetLog(prescription: slot, index: $0.offset, load: 100, reps: $0.element, rir: rir, occurredAt: date) }
        session.status = .completed; session.endedAt = date.addingTimeInterval(1800)
        return session
    }
    func qualified() -> AthleteState {
        var state = fixture(); state.sessions = [exposure(state, daysAgo: 5), exposure(state, daysAgo: 2)]; return state
    }
    /// Read-only evaluation of `request` against `state` through the core; nothing is persisted.
    func decision(_ state: AthleteState, request: Request? = nil, library: ContentLibrary? = nil) -> Decision {
        let request = request ?? .progression(state.nextPlan!.slots[0].id)
        do { return try core.decide(state: state, request: request, library: library ?? self.library, now: now) }
        catch {
            XCTFail("Core call failed: \(error)")
            return Decision(.withholdGuidance, "TEST_CORE_FAILURE", String(describing: error))
        }
    }
    func service(_ state: AthleteState, storage: MemoryPersistence = MemoryPersistence()) throws -> TrainerService {
        storage.data = try JSONEncoder().encode(state)
        return TrainerService(repository: try StateRepository(persistence: storage), library: library, core: core)
    }
    func testQualifyingFixtureProposes105AndThreeBy8() {
        let result = decision(qualified())
        XCTAssertEqual(result.reason, "QUALIFYING_EXPOSURES_COMPLETE")
        XCTAssertEqual(result.after?.slots[0].load, 105)
        XCTAssertEqual(result.after?.slots[0].targets, [8, 8, 8])
        XCTAssertEqual(result.after?.slots[0].workingSets, 3)
        XCTAssertEqual(result.evidence.count, 6)
    }
    func testMissingEffortRemainsUnknown() {
        var state = fixture(); state.sessions = [exposure(state, daysAgo: 1, rir: nil)]
        XCTAssertEqual(decision(state).reason, "EFFORT_UNKNOWN")
        XCTAssertNil(state.sessions[0].logs[0].rir)
    }
    func testExcessiveIncrementNotRoundedUp() {
        var state = qualified(); state.program!.plans[0].slots[0].equipment.availableLoads = [100, 110]
        XCTAssertEqual(decision(state).reason, "INCREMENT_EXCEEDS_BOUND")
    }
    func testRepProgressionAllocatesOneTotalRep() {
        var state = fixture(); state.sessions = [exposure(state, daysAgo: 1, reps: [9, 8, 8])]
        XCTAssertEqual(decision(state).after?.slots[0].targets, [10, 8, 8])
        XCTAssertEqual(decision(state).after?.slots[0].load, 100)
    }
    func testIncompleteExposureNotStrengthFailure() {
        var state = fixture(); state.sessions = [exposure(state, daysAgo: 1, reps: [10, 10])]
        XCTAssertEqual(decision(state).reason, "INCOMPLETE_EXPOSURE")
    }
    func testModifiedExposureBreaksStreak() {
        var state = qualified(); state.sessions[1].plan.modified = true
        XCTAssertEqual(decision(state).reason, "MODIFIED_EXPOSURE")
    }
    func testFailedMiddleExposureBreaksStreak() {
        var state = fixture()
        state.sessions = [exposure(state, daysAgo: 6), exposure(state, daysAgo: 4, reps: [8, 8, 8]), exposure(state, daysAgo: 1)]
        XCTAssertEqual(decision(state).reason, "MORE_EXPOSURES_REQUIRED")
    }
    func testStaleHistoryRequiresReconfirmation() {
        var state = fixture(); state.sessions = [exposure(state, daysAgo: 29)]
        XCTAssertEqual(decision(state).reason, "HISTORY_STALE")
    }
    func testLongGapDoesNotQualify() {
        var state = fixture(); state.sessions = [exposure(state, daysAgo: 20), exposure(state, daysAgo: 1)]
        XCTAssertEqual(decision(state).reason, "MORE_EXPOSURES_REQUIRED")
    }
    func testPainBeatsQualifyingHistory() {
        var state = qualified(); state.painExclusions.insert("bench")
        XCTAssertEqual(decision(state).reason, "REPORTED_PAIN")
    }
    func testExclusionBeatsPreference() {
        var state = qualified(); state.profile!.excludedExercises.insert("bench"); state.profile!.preferredExercises.insert("bench")
        XCTAssertEqual(decision(state).reason, "EXERCISE_EXCLUDED")
    }
    func testProductionRejectsFixturePolicy() {
        let state = fixture()
        XCTAssertEqual(decision(state, library: ContentLibrary()).reason, "POLICY_NOT_APPROVED")
        XCTAssertThrowsError(try core.initialProgram(profile: state.profile!, library: ContentLibrary(), now: now))
    }
    func testMissingRequiredProfileDoesNotInventProgram() {
        XCTAssertThrowsError(try core.initialProgram(profile: Profile(), library: library, now: now))
    }
    func testSubstitutionClearsOriginalLoad() {
        let state = fixture(), id = fixture().athleteID // IDs are independent; never used for inference.
        XCTAssertNotEqual(id, state.athleteID)
        let result = decision(state, request: .substitute(state.nextPlan!.slots[0].id, "machine_press"))
        XCTAssertEqual(result.outcome, .proposeChange)
        XCTAssertNil(result.after?.slots[0].load)
        XCTAssertEqual(result.after?.slots[0].equipment.basis, .machineSetting)
        XCTAssertNotEqual(result.after?.slots[0].comparisonKey, state.nextPlan!.slots[0].comparisonKey)
    }
    func testUnsupportedSubstitutionDoesNotWrite() {
        let state = fixture()
        XCTAssertEqual(decision(state, request: .substitute(state.nextPlan!.slots[0].id, "made_up")).outcome, .withholdGuidance)
    }
    func testShorteningPreservesRestAndWarmup() {
        var state = fixture()
        var extra = state.nextPlan!.slots[0]; extra.id = UUID(); extra.optional = true
        state.program!.plans[0].slots.append(extra)
        let result = decision(state, request: .shorten(20))
        XCTAssertEqual(result.after?.slots.count, 1)
        XCTAssertEqual(result.after?.slots[0].restSeconds, 120)
        XCTAssertEqual(result.after?.warmUpMinutes, 5)
    }
    func testRequiredWorkCannotBeSilentlyCompressed() {
        XCTAssertEqual(decision(fixture(), request: .shorten(5)).reason, "REQUIRED_WORK_DOES_NOT_FIT")
    }
    func testRepeatedSaveCreatesOneSet() throws {
        let service = try service(fixture()); try service.start(now: now)
        let session = service.repository.snapshot.activeSession!
        let log = SetLog(prescription: session.plan.slots[0], index: 0, load: 100, reps: 10, rir: nil, occurredAt: now)
        try service.saveSet(log, sessionID: session.id); try service.saveSet(log, sessionID: session.id)
        XCTAssertEqual(service.repository.snapshot.activeSession!.logs.count, 1)
    }
    func testOperationIDReuseWithChangedPayloadFails() throws {
        let service = try service(fixture()); try service.start(now: now)
        let session = service.repository.snapshot.activeSession!
        var log = SetLog(prescription: session.plan.slots[0], index: 0, load: 100, reps: 10, rir: 2)
        try service.saveSet(log, sessionID: session.id); log.reps = 12
        XCTAssertThrowsError(try service.saveSet(log, sessionID: session.id))
    }
    func testFailedSaveDoesNotPublishCandidateState() throws {
        let storage = MemoryPersistence(), service = try service(fixture(), storage: storage)
        let before = service.repository.snapshot; storage.failWrites = true
        XCTAssertThrowsError(try service.start(now: now))
        XCTAssertEqual(service.repository.snapshot, before)
    }
    func testResumeAfterReloadRetainsSessionAndRest() throws {
        let storage = MemoryPersistence(), service = try service(fixture(), storage: storage)
        try service.start(now: now); let session = service.repository.snapshot.activeSession!
        try service.saveSet(SetLog(prescription: session.plan.slots[0], index: 0, load: 100, reps: 10, rir: 2, occurredAt: now), sessionID: session.id)
        try service.setPaused(true)
        let restored = try StateRepository(persistence: storage)
        XCTAssertEqual(restored.snapshot.activeSession?.id, session.id)
        XCTAssertEqual(restored.snapshot.activeSession?.status, .paused)
        XCTAssertEqual(restored.snapshot.activeSession?.restEndsAt, now.addingTimeInterval(120))
    }
    func testCorruptStoreIsNotOverwritten() {
        let data = Data("bad-json".utf8), storage = MemoryPersistence(data: Data("bad-json".utf8))
        XCTAssertThrowsError(try StateRepository(persistence: storage))
        XCTAssertEqual(storage.data, data)
    }
    func testZeroRepsAreNotMissing() throws {
        let service = try service(fixture()); try service.start(now: now)
        let session = service.repository.snapshot.activeSession!
        try service.saveSet(SetLog(prescription: session.plan.slots[0], index: 0, load: nil, reps: 0, rir: nil), sessionID: session.id)
        XCTAssertEqual(service.repository.snapshot.activeSession?.logs.first?.reps, 0)
        XCTAssertNil(service.repository.snapshot.activeSession?.logs.first?.load)
    }
    func testNegativeOrNonfiniteLoadIsRejected() throws {
        let service = try service(fixture()); try service.start(now: now)
        let session = service.repository.snapshot.activeSession!, slot = session.plan.slots[0]
        XCTAssertThrowsError(try service.saveSet(SetLog(prescription: slot, index: 0, load: .infinity, reps: 8, rir: 2), sessionID: session.id))
        XCTAssertThrowsError(try service.saveSet(SetLog(prescription: slot, index: 0, load: -1, reps: 8, rir: 2), sessionID: session.id))
        XCTAssertThrowsError(try service.saveSet(SetLog(prescription: slot, index: 0, load: 100, reps: 8, rir: 11), sessionID: session.id))
        XCTAssertTrue(service.repository.snapshot.activeSession!.logs.isEmpty)
    }
    func testUnitConversionDoesNotMutateHistory() {
        let state = qualified(), original = state.sessions[0].logs[0]
        XCTAssertEqual(MassUnit.lb.convert(100, to: .kg), 45.359237, accuracy: 0.000001)
        XCTAssertEqual(original, state.sessions[0].logs[0])
    }
    func testActiveSessionBlocksProposal() throws {
        let service = try service(qualified()); try service.start(now: now)
        XCTAssertEqual(decision(service.repository.snapshot).reason, "SESSION_ACTIVE")
    }
    func testAcceptanceIsIdempotent() throws {
        let service = try service(qualified()), slotID = service.repository.snapshot.nextPlan!.slots[0].id
        try service.request(.progression(slotID), now: now)
        let id = service.repository.snapshot.recommendations.last!.id
        try service.acceptRecommendation(id: id, now: now); try service.acceptRecommendation(id: id, now: now)
        XCTAssertEqual(service.repository.snapshot.nextPlan!.slots[0].load, 105)
        XCTAssertEqual(service.repository.snapshot.events.filter { $0.name == "recommendation_applied" }.count, 1)
    }
    func testCorrectionExpiresDependentProposal() throws {
        let service = try service(qualified()), snapshot = service.repository.snapshot
        try service.request(.progression(snapshot.nextPlan!.slots[0].id), now: now)
        let id = service.repository.snapshot.recommendations.last!.id, session = snapshot.sessions[1], log = session.logs[2]
        try service.correctSet(sessionID: session.id, logID: log.id, expectedRevision: 1, load: 100, reps: 8, rir: 2, now: now)
        XCTAssertEqual(service.repository.snapshot.recommendations.last?.status, .expired)
        XCTAssertThrowsError(try service.acceptRecommendation(id: id, now: now))
        XCTAssertEqual(service.repository.snapshot.nextPlan?.slots[0].load, 100)
    }
    func testConflictBlocksProgressionUntilExplicitResolution() throws {
        let service = try service(qualified()), session = service.repository.snapshot.sessions[1], log = session.logs[0]
        XCTAssertFalse(try service.correctSet(sessionID: session.id, logID: log.id, expectedRevision: 0, load: 100, reps: 12, rir: 2))
        XCTAssertEqual(decision(service.repository.snapshot).reason, "EVIDENCE_CONFLICT")
        let conflict = service.repository.snapshot.conflicts[0]
        try service.resolveConflict(id: conflict.id, useIncoming: false)
        XCTAssertTrue(service.repository.snapshot.conflicts.isEmpty)
        XCTAssertEqual(service.repository.snapshot.sessions[1].logs[0].reps, 10)
    }
    func testRejectDoesNotInferDislike() throws {
        let service = try service(qualified()), before = service.repository.snapshot.profile
        try service.request(.progression(service.repository.snapshot.nextPlan!.slots[0].id), now: now)
        try service.rejectRecommendation(id: service.repository.snapshot.recommendations.last!.id, reason: "equipment_unavailable")
        XCTAssertEqual(service.repository.snapshot.profile, before)
    }
    func testEarlyEndPreservesOmissionReason() throws {
        let service = try service(fixture()); try service.start(now: now); try service.finish(reason: .time, now: now)
        XCTAssertEqual(service.repository.snapshot.sessions.last?.status, .endedEarly)
        XCTAssertEqual(Set(service.repository.snapshot.sessions.last!.omissions.values), [.time])
    }
    func testSkipDoesNotDoubleNextWork() throws {
        let service = try service(fixture()), before = service.repository.snapshot.nextPlan
        try service.skip(now: now)
        XCTAssertEqual(service.repository.snapshot.nextPlan, before)
        XCTAssertEqual(service.repository.snapshot.sessions.last?.status, .skipped)
    }
    func testDeleteRemovesDependentRecords() throws {
        let service = try service(qualified())
        try service.request(.progression(service.repository.snapshot.nextPlan!.slots[0].id), now: now)
        try service.deleteSession(id: service.repository.snapshot.sessions[1].id)
        XCTAssertTrue(service.repository.snapshot.recommendations.isEmpty)
        try service.repository.deleteAll()
        XCTAssertNil(service.repository.snapshot.profile)
        XCTAssertTrue(service.repository.snapshot.sessions.isEmpty)
    }
    func testReplayProducesIdenticalDecision() {
        let state = qualified(); XCTAssertEqual(decision(state), decision(state))
    }
    func testProgramReplacementPreservesCompletedHistory() throws {
        let service = try service(qualified()), before = service.repository.snapshot.sessions
        try service.acceptInitialPlan(profile: service.repository.snapshot.profile!, now: now)
        XCTAssertEqual(service.repository.snapshot.sessions, before)
        XCTAssertEqual(service.repository.snapshot.previousPrograms.count, 1)
    }
    func testTemporaryOverrideDoesNotReplaceBaseProgram() throws {
        let service = try service(fixture()), before = service.repository.snapshot.program
        try service.request(.substitute(service.repository.snapshot.nextPlan!.slots[0].id, "machine_press"), now: now)
        try service.acceptRecommendation(id: service.repository.snapshot.recommendations.last!.id, now: now)
        XCTAssertEqual(service.repository.snapshot.program, before)
        XCTAssertEqual(service.repository.snapshot.nextPlan?.slots[0].exerciseID, "machine_press")
        try service.start(now: now); try service.finish(reason: .time, now: now)
        XCTAssertEqual(service.repository.snapshot.nextPlan?.slots[0].exerciseID, "bench")
    }
    func testNutritionPortionsAndDailyTotals() throws {
        let service = try service(fixture())
        let nutrients = try service.scaleNutrients(Nutrients(calories: 200, protein: 10, carbs: 20, fat: 9), servings: 1.5)
        XCTAssertEqual(nutrients.calories, 300)
        let meal = Meal(name: "Fixture", nutrients: nutrients, occurredAt: now)
        XCTAssertEqual(Meal.total([meal], on: now).protein, 15)
        XCTAssertThrowsError(try service.scaleNutrients(nutrients, servings: -1))
    }
    func testMealLoggingDoesNotChangeTrainingDecision() throws {
        let service = try service(qualified()), before = decision(service.repository.snapshot)
        try service.saveMeal(Meal(name: "Example", nutrients: Nutrients(calories: 100)))
        XCTAssertEqual(decision(service.repository.snapshot), before)
    }
    func testPoseDropoutCannotProducePhantomRep() {
        var counter = CurlCounter()
        let a = PosePoint(x: 0, y: 1, confidence: 1), b = PosePoint(x: 0, y: 0, confidence: 1)
        let extended = PosePoint(x: 0, y: -1, confidence: 1), flexed = PosePoint(x: 0.5, y: 1, confidence: 1)
        for t in [0.0, 0.1, 0.2] { _ = counter.consume(shoulder: a, elbow: b, wrist: extended, timestamp: t) }
        for t in [0.3, 0.4, 0.5] { _ = counter.consume(shoulder: a, elbow: b, wrist: flexed, timestamp: t) }
        _ = counter.consume(shoulder: nil, elbow: nil, wrist: nil, timestamp: 0.6)
        for t in [0.7, 0.8, 0.9] { _ = counter.consume(shoulder: a, elbow: b, wrist: extended, timestamp: t) }
        XCTAssertEqual(counter.observation.count, 0)
    }
    func testPoseFullCycleCountsOne() {
        var counter = CurlCounter()
        let a = PosePoint(x: 0, y: 1, confidence: 1), b = PosePoint(x: 0, y: 0, confidence: 1)
        let e = PosePoint(x: 0, y: -1, confidence: 1), f = PosePoint(x: 0.5, y: 1, confidence: 1)
        for i in 0..<12 {
            _ = counter.consume(shoulder: a, elbow: b, wrist: (4..<8).contains(i) ? f : e, timestamp: Double(i) * 0.1)
        }
        XCTAssertEqual(counter.observation.count, 1)
        XCTAssertNotNil(counter.observation.lastDuration)
    }
    func testBenchmarkReportsMeasuredPercentile() {
        var benchmark = Benchmark(); [10.0, 20, 30, 40, 50].forEach { benchmark.record(milliseconds: $0) }
        XCTAssertEqual(benchmark.percentile(0.5), 30)
        XCTAssertEqual(benchmark.percentile(0.95), 50)
    }
    func testMealCorrectionRetainsAuditAndRejectsStaleEdit() throws {
        let service = try service(fixture())
        var meal = Meal(name: "Meal", nutrients: Nutrients(calories: 100))
        try service.saveMeal(meal); meal.nutrients.calories = 150
        try service.saveMeal(meal)
        XCTAssertEqual(service.repository.snapshot.mealAudits[0].previous.nutrients.calories, 100)
        XCTAssertThrowsError(try service.saveMeal(meal))
        try service.deleteMeal(id: meal.id)
        XCTAssertTrue(service.repository.snapshot.mealAudits.isEmpty)
    }
    func testExcludingActiveExercisePausesSession() throws {
        let service = try service(fixture()); try service.start(now: now)
        try service.exclude(exerciseID: "bench", excluded: true)
        XCTAssertEqual(service.repository.snapshot.activeSession?.status, .paused)
        XCTAssertThrowsError(try service.setPaused(false))
    }
    func testNewEquipmentContextCannotBorrowHistory() {
        var state = qualified(); state.program!.plans[0].slots[0].equipment.id = "different-rack"
        XCTAssertEqual(decision(state).reason, "NO_COMPARABLE_HISTORY")
    }
    func testUnknownEquipmentStepsBlockIncrease() {
        var state = qualified(); state.program!.plans[0].slots[0].equipment.availableLoads = []
        XCTAssertEqual(decision(state).reason, "EQUIPMENT_STEP_UNKNOWN")
    }
    func testEffortBelowPolicyHoldsLoad() {
        var state = fixture(); state.sessions = [exposure(state, daysAgo: 1, rir: 0)]
        XCTAssertEqual(decision(state).reason, "TARGET_NOT_QUALIFIED")
    }
    func testDuplicateWorkingIndexIsNotAnExtraSet() throws {
        let service = try service(fixture()); try service.start(now: now)
        let session = service.repository.snapshot.activeSession!, slot = session.plan.slots[0]
        try service.saveSet(SetLog(prescription: slot, index: 0, load: 100, reps: 8, rir: 2), sessionID: session.id)
        XCTAssertThrowsError(try service.saveSet(SetLog(prescription: slot, index: 0, load: 100, reps: 8, rir: 2), sessionID: session.id))
    }
}
