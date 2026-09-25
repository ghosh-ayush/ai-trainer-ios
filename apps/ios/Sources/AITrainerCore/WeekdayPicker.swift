import SwiftUI

/// Seven day buttons, Monday first, that toggle which weekdays are free (ADR-017, ADR-025).
/// Each button reads its full day name and state to VoiceOver ("Monday free", "Monday not free").
public struct WeekdayPicker: View {
    @Binding private var freeDays: [Int]

    /// - Parameter freeDays: weekdays 0-6 (Monday = 0), kept sorted.
    public init(freeDays: Binding<[Int]>) {
        _freeDays = freeDays
    }

    public var body: some View {
        HStack(spacing: 6) {
            ForEach(0..<7, id: \.self) { day in
                let free = freeDays.contains(day)
                Button { toggle(day) } label: { Text(Weekday.initial(day)).lineLimit(1) }
                    .buttonStyle(.stitch(free ? .primary : .secondary, compact: true))
                    .accessibilityLabel("\(Weekday.name(day)) \(free ? "free" : "not free")")
            }
        }
    }

    private func toggle(_ day: Int) {
        var days = Set(freeDays)
        if days.contains(day) {
            days.remove(day)
        } else {
            days.insert(day)
        }
        freeDays = days.sorted()
    }
}
