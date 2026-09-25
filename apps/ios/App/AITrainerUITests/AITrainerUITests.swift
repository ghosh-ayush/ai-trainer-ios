import XCTest

/// End-to-end flows through the real app, driven like an athlete would. Each test launches with
/// `--ui-testing`, so the app starts from an empty in-memory state and never touches saved data.
/// Rules are covered by the Python and Swift tests; these check the screens that show them.
final class AITrainerUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["--ui-testing"]
        app.launch()
    }

    /// Onboarding on three free days leads to a previewed week that, once accepted, is Today's plan.
    @MainActor
    func testOnboardingOnFreeDaysAcceptsAWeek() throws {
        onboard()
        XCTAssertTrue(app.buttons["Start"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["Less time"].exists)
        XCTAssertTrue(app.buttons["Ask the app"].exists, "The chat head is on Today")
    }

    /// The weekday picker says which days are free, and its labels are shown for review.
    @MainActor
    func testWeekdayButtonsToggleAndSayWhichDaysAreFree() throws {
        let monday = app.buttons["Monday not free"]
        XCTAssertTrue(monday.waitForExistence(timeout: 10))
        attachScreenshot(named: "Weekday buttons before choosing")
        monday.tap()
        XCTAssertTrue(app.buttons["Monday free"].waitForExistence(timeout: 5))
        app.buttons["Monday free"].tap()
        XCTAssertTrue(app.buttons["Monday not free"].waitForExistence(timeout: 5))
    }

    /// A set exactly as planned needs no "Same as last" (it would repeat "Done as planned"). After a
    /// set with a different rep count, the next set offers "Same as last" with those reps.
    @MainActor
    func testLoggingASetOffersSameAsLastOnlyWhenItDiffersFromThePlan() throws {
        onboard()
        app.buttons["Start"].tap()
        let done = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "Done as planned · ")).firstMatch
        XCTAssertTrue(done.waitForExistence(timeout: 10))
        let plannedReps = try XCTUnwrap(Self.reps(in: done.label), "The button says how many reps")
        let sameAsLast = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "Same as last · "))

        done.tap()
        XCTAssertTrue(loggedSets(reps: plannedReps).firstMatch.waitForExistence(timeout: 10))
        XCTAssertEqual(sameAsLast.count, 0, "A set as planned offers no Same as last")

        tapWhenVisible(app.buttons["Adjust · warm-up · extra set"])
        let increase = app.buttons.matching(identifier: "Increase")
        XCTAssertTrue(increase.element(boundBy: 1).waitForExistence(timeout: 10))
        increase.element(boundBy: 1).tap()  // load comes first; this is reps
        tapWhenVisible(app.buttons["Save set"])
        XCTAssertTrue(loggedSets(reps: plannedReps + 1).firstMatch.waitForExistence(timeout: 10))

        let same = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "Same as last · \(plannedReps + 1) reps")).firstMatch
        XCTAssertTrue(same.waitForExistence(timeout: 10))
        tapWhenVisible(same)
        XCTAssertTrue(waitForCount(loggedSets(reps: plannedReps + 1), toBe: 2), "Same as last logged the same reps again")
    }

    /// Chat answers a tapped question, offers pain actions, marks an injury and ends it again.
    @MainActor
    func testChatAnswersPainAndEndsAStatus() throws {
        onboard()
        app.buttons["Ask the app"].tap()
        tapWhenVisible(app.buttons["Something hurts"])
        XCTAssertTrue(app.staticTexts["The app can't assess pain or tell which exercises are safe with it."]
            .waitForExistence(timeout: 10))
        tapWhenVisible(app.buttons["Mark me injured (pauses suggestions)"])
        let marked = app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH %@", "Marked injured until you tap I'm back")).firstMatch
        XCTAssertTrue(marked.waitForExistence(timeout: 10))

        tapWhenVisible(app.buttons["I'm sick or away"])
        XCTAssertTrue(app.staticTexts["You are marked injured. Tap I'm back to resume the app's suggestions."]
            .waitForExistence(timeout: 10))
        // Today's banner behind the sheet also says "I'm back"; chat's own button has its identifier.
        // Scroll to it, since the new reply may still be scrolling into view on a slower simulator.
        tapWhenVisible(app.buttons["chat.endStatus"])
        XCTAssertTrue(app.staticTexts["Welcome back. The app's suggestions are on again."].waitForExistence(timeout: 10))

        app.buttons["Cancel"].firstMatch.tap()
        XCTAssertTrue(app.buttons["Taking a break, sick or injured?"].waitForExistence(timeout: 10),
                      "Today no longer shows the injury")
    }

    /// ADR-025: new free days get a proposed week; Accept on Today applies it, and You shows the days.
    @MainActor
    func testChangingFreeDaysProposesAWeekToAccept() throws {
        onboard()
        app.tabBars.buttons["YOU"].tap()
        tapWhenVisible(app.buttons["Change free days and minutes"])
        tapWhenVisible(app.buttons["Tuesday not free"])
        XCTAssertTrue(app.buttons["Tuesday free"].waitForExistence(timeout: 5))
        tapWhenVisible(app.buttons["See weeks for these days"])
        tapWhenVisible(app.buttons["Propose the suggested week"])
        let accept = app.buttons["Accept"]
        XCTAssertTrue(accept.waitForExistence(timeout: 10), "The new week waits on Today for Accept")
        tapWhenVisible(accept)
        app.tabBars.buttons["YOU"].tap()
        let profile = app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH %@", "Mon, Tue, Wed, Fri")).firstMatch
        XCTAssertTrue(profile.waitForExistence(timeout: 10), "You shows the new free days")
    }

    /// ADR-026: another session of the week for today, proposed and swapped on Accept.
    @MainActor
    func testDoingADifferentSessionTodaySwapsItIn() throws {
        onboard()
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH %@", "Full body A")).firstMatch
            .waitForExistence(timeout: 10))
        tapWhenVisible(app.buttons["Do a different session today"])
        let chosen = app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH %@", "Full body B · ")).firstMatch
        XCTAssertTrue(chosen.waitForExistence(timeout: 10), "The sheet lists the week's other sessions")
        tapWhenVisible(app.buttons["Do this today"])
        tapWhenVisible(app.buttons["Accept"])
        let today = app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH %@", "Full body B · ")).firstMatch
        XCTAssertTrue(today.waitForExistence(timeout: 10), "Today's session is now the chosen one")
    }

    // MARK: Steps

    /// Consent, Monday / Wednesday / Friday, the suggested week, Accept.
    private func onboard() {
        let consent = app.switches["Consent"]
        XCTAssertTrue(consent.waitForExistence(timeout: 15))
        turnOn(consent)
        for day in ["Monday", "Wednesday", "Friday"] {
            tapWhenVisible(app.buttons["\(day) not free"])
            XCTAssertTrue(app.buttons["\(day) free"].waitForExistence(timeout: 5))
        }
        tapWhenVisible(app.buttons["See my week options"])
        tapWhenVisible(app.buttons["Preview the suggested week"])
        tapWhenVisible(app.buttons["Accept plan"])
    }

    /// Switches a toggle on. A tap on the switch is tried first, then a drag of its knob, which is
    /// what the iOS 26 simulator needed when driven by hand.
    private func turnOn(_ toggle: XCUIElement) {
        if Self.isOn(toggle) { return }
        toggle.tap()
        if Self.isOn(toggle) { return }
        let knob = toggle.coordinate(withNormalizedOffset: CGVector(dx: 0.3, dy: 0.5))
        knob.press(forDuration: 0.1, thenDragTo: toggle.coordinate(withNormalizedOffset: CGVector(dx: 0.95, dy: 0.5)))
        XCTAssertTrue(Self.isOn(toggle), "The toggle turned on")
    }

    /// Scrolls toward the first element matching `element` until it can be tapped, then taps it.
    /// Short drags up or down, depending on which side of the screen the element is on, so a long
    /// list (a workout has one "Adjust" per exercise) is not overshot.
    private func tapWhenVisible(_ element: XCUIElement, file: StaticString = #filePath, line: UInt = #line) {
        let target = element.firstMatch
        XCTAssertTrue(target.waitForExistence(timeout: 10), "\(element) exists", file: file, line: line)
        let screen = app.windows.firstMatch.frame
        var drags = 0
        while !target.isHittable && drags < 16 {
            let below = target.frame.midY > screen.midY
            let start = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: below ? 0.7 : 0.35))
            let end = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: below ? 0.4 : 0.65))
            start.press(forDuration: 0.05, thenDragTo: end)
            drags += 1
        }
        XCTAssertTrue(target.isHittable, "\(element) can be tapped", file: file, line: line)
        target.tap()
    }

    /// Logged set rows whose result starts with `reps` ("9 reps @ unknown load").
    private func loggedSets(reps: Int) -> XCUIElementQuery {
        app.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@", " \(reps) reps @"))
    }

    private func waitForCount(_ query: XCUIElementQuery, toBe count: Int, timeout: TimeInterval = 10) -> Bool {
        let expectation = XCTNSPredicateExpectation(predicate: NSPredicate(format: "count == %d", count), object: query)
        return XCTWaiter().wait(for: [expectation], timeout: timeout) == .completed
    }

    private func attachScreenshot(named name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    private static func isOn(_ toggle: XCUIElement) -> Bool {
        (toggle.value as? String) == "1"
    }

    /// The rep count in "Done as planned · 8 reps · load unknown".
    private static func reps(in label: String) -> Int? {
        let parts = label.components(separatedBy: " · ")
        guard parts.count > 1 else { return nil }
        return Int(parts[1].components(separatedBy: " ").first ?? "")
    }
}
