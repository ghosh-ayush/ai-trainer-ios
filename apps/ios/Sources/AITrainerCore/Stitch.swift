import SwiftUI
import CoreText

// The "Stitch" design system from the Figma file "AI Trainer — Complete iOS App" (page 07 Stitch kit):
// tokens, type styles and the S/* components the P1 screens are built from. It lives in the package
// rather than the app target because app-target files are added through Xcode (ADR-011); package
// files are picked up automatically. Views only — no rules, no state.

// MARK: - Tokens (names follow the Figma variables)

public enum Stitch {
    public static let bgPage = Color(hex: 0x10141A)
    public static let textPrimary = Color(hex: 0xDFE2EB)
    public static let textSecondary = Color(hex: 0xC7C4D7)
    public static let textMuted = Color(hex: 0x908FA0)
    public static let textDisabled = Color(hex: 0x464554)
    public static let accentPrimary = Color(hex: 0xC0C1FF)
    public static let accentOn = Color(hex: 0x1000A9)
    public static let accentSoft = Color(hex: 0x8083FF)
    public static let warnPrimary = Color(hex: 0xFFB95F)
    public static let tintAmber = Color(hex: 0x3B3226)
    public static let dangerPrimary = Color(hex: 0xFFB4AB)
    public static let dangerBg = Color(hex: 0x3B1C1F)
    public static let strokeHairline = Color(hex: 0x262A31)
    public static let glassSurface = Color.white.opacity(0.06)
    public static let glassSurface2 = Color.white.opacity(0.10)
    public static let glassStroke = Color.white.opacity(0.10)
    public static let glassInset = Color.white.opacity(0.04)
    public static let glassDeep = Color.black.opacity(0.28)
    public static let glassChrome = Color(hex: 0x10141A, opacity: 0.78)
    public static let glassSheet = Color(hex: 0x10141A, opacity: 0.92)
    public static let backdropLavender = Color(hex: 0x8083FF, opacity: 0.22)
    public static let backdropAmber = Color(hex: 0xFFB95F, opacity: 0.10)

    /// Registers the bundled fonts with Core Text once per process. Safe to call repeatedly.
    public static func registerFonts() { _ = fontRegistration }
    private static let fontRegistration: Void = {
        let urls = (Bundle.module.urls(forResourcesWithExtension: "ttf", subdirectory: nil) ?? [])
            + (Bundle.module.urls(forResourcesWithExtension: "ttf", subdirectory: "Fonts") ?? [])
        for url in urls {
            CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil)
        }
    }()
}

extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        self.init(.sRGB, red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255, opacity: opacity)
    }
}

// MARK: - Type styles (Figma text styles "Stitch/…"; each scales with Dynamic Type)

public enum StitchType {
    case displayTitle, displayH2, displayH3
    case body15, bodyMedium15, body13, bodyMedium13, bodyMedium12
    case monoLabel, monoLabelMedium, monoSmall, monoBody, monoBodyBold, monoNumber, monoNumberLarge

    var font: Font {
        switch self {
        case .displayTitle: return .custom("SpaceGrotesk-Bold", size: 28, relativeTo: .largeTitle)
        case .displayH2: return .custom("SpaceGrotesk-Bold", size: 20, relativeTo: .title3)
        case .displayH3: return .custom("SpaceGrotesk-Bold", size: 16, relativeTo: .headline)
        case .body15: return .custom("Inter-Regular", size: 15, relativeTo: .body)
        case .bodyMedium15: return .custom("Inter-Medium", size: 15, relativeTo: .body)
        case .body13: return .custom("Inter-Regular", size: 13, relativeTo: .footnote)
        case .bodyMedium13: return .custom("Inter-Medium", size: 13, relativeTo: .footnote)
        case .bodyMedium12: return .custom("Inter-Medium", size: 12, relativeTo: .caption)
        case .monoLabel: return .custom("JetBrainsMono-Bold", size: 11, relativeTo: .caption2)
        case .monoLabelMedium: return .custom("JetBrainsMono-Medium", size: 11, relativeTo: .caption2)
        case .monoSmall: return .custom("JetBrainsMono-Medium", size: 12, relativeTo: .caption)
        case .monoBody: return .custom("JetBrainsMono-Medium", size: 15, relativeTo: .body)
        case .monoBodyBold: return .custom("JetBrainsMono-Bold", size: 15, relativeTo: .body)
        case .monoNumber: return .custom("JetBrainsMono-Bold", size: 22, relativeTo: .title2)
        case .monoNumberLarge: return .custom("JetBrainsMono-Bold", size: 32, relativeTo: .largeTitle)
        }
    }
    var tracking: CGFloat {
        switch self {
        case .displayTitle: return -0.7
        case .displayH2: return -0.5
        case .body15, .bodyMedium15: return -0.075
        case .monoLabel: return 0.55
        case .monoLabelMedium: return 0.275
        case .monoBody, .monoBodyBold: return -0.15
        case .monoNumber: return -0.44
        case .monoNumberLarge: return -0.8
        default: return 0
        }
    }
}

extension View {
    /// Applies a Stitch text style: font plus the style's tracking.
    public func stitch(_ type: StitchType) -> some View { font(type.font).tracking(type.tracking) }
}

// MARK: - Surfaces

public enum StitchTone: String {
    case `default`, accent, warn, danger

    public init(name: String) { self = StitchTone(rawValue: name) ?? .default }
    var stroke: Color {
        switch self {
        case .default: return Stitch.glassStroke
        case .accent: return Stitch.accentSoft
        case .warn: return Stitch.warnPrimary
        case .danger: return Stitch.dangerPrimary
        }
    }
}

/// Screen background: page color with the soft lavender and amber glows behind the glass.
public struct StitchBackdrop: View {
    public init() {}
    public var body: some View {
        ZStack {
            Stitch.bgPage
            RadialGradient(colors: [Stitch.backdropLavender, .clear], center: UnitPoint(x: 0.05, y: 0.4), startRadius: 0, endRadius: 360)
            RadialGradient(colors: [Stitch.backdropAmber, .clear], center: UnitPoint(x: 1.0, y: 0.95), startRadius: 0, endRadius: 320)
        }
        .ignoresSafeArea()
    }
}

/// A glass surface: translucent fill, hairline stroke tinted by tone, inner top highlight, soft shadow.
struct GlassSurface: ViewModifier {
    var tone: StitchTone = .default
    var radius: CGFloat = 12
    var fill: Color = Stitch.glassSurface
    func body(content: Content) -> some View {
        let shape = RoundedRectangle(cornerRadius: radius, style: .continuous)
        content
            .background(fill, in: shape)
            .overlay(shape.strokeBorder(tone.stroke, lineWidth: 1))
            .overlay(alignment: .top) {
                shape.stroke(Color.white.opacity(0.1), lineWidth: 1).mask(alignment: .top) { Rectangle().frame(height: 1) }
            }
            .shadow(color: .black.opacity(0.25), radius: 12, y: 8)
    }
}

extension View {
    public func glass(_ tone: StitchTone = .default, radius: CGFloat = 12, fill: Color = Stitch.glassSurface) -> some View {
        modifier(GlassSurface(tone: tone, radius: radius, fill: fill))
    }
}

// MARK: - Components

/// S/Card: a surface with a title and body, or any content.
public struct StitchCard<Content: View>: View {
    let tone: StitchTone
    let content: Content
    public init(tone: StitchTone = .default, @ViewBuilder content: () -> Content) {
        self.tone = tone; self.content = content()
    }
    public var body: some View {
        VStack(alignment: .leading, spacing: 8) { content }
            .padding(16).frame(maxWidth: .infinity, alignment: .leading)
            .glass(tone)
    }
}

extension StitchCard where Content == StitchCardText {
    public init(_ title: String, body: String, tone: StitchTone = .default) {
        self.init(tone: tone) { StitchCardText(title: title, text: body) }
    }
}

public struct StitchCardText: View {
    let title: String
    let text: String
    public init(title: String, text: String) { self.title = title; self.text = text }
    public var body: some View {
        Text(title).stitch(.displayH3).foregroundStyle(Stitch.textPrimary)
        Text(text).stitch(.body13).foregroundStyle(Stitch.textSecondary)
    }
}

/// S/SectionLabel: uppercase mono header with optional right-aligned meta.
public struct StitchSectionLabel: View {
    let label: String
    let meta: String
    public init(_ label: String, meta: String = "") { self.label = label; self.meta = meta }
    public var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label).foregroundStyle(Stitch.textMuted)
            Spacer(minLength: 8)
            Text(meta).foregroundStyle(Stitch.accentPrimary).multilineTextAlignment(.trailing)
        }
        .stitch(.monoLabel).textCase(.uppercase)
        .accessibilityElement(children: .combine).accessibilityAddTraits(.isHeader)
    }
}

/// S/Pill: compact badge. Amber = preview fixture, lavender = governed, danger = destructive.
public struct StitchPill: View {
    public enum Tone { case amber, lavender, danger }
    let label: String
    let tone: Tone
    public init(_ label: String, tone: Tone = .amber) { self.label = label; self.tone = tone }
    public var body: some View {
        Text(label).stitch(.monoLabel).textCase(.uppercase).lineLimit(1)
            .foregroundStyle(tone == .amber ? Stitch.warnPrimary : tone == .danger ? Stitch.dangerPrimary : Stitch.accentPrimary)
            .padding(.horizontal, 8).padding(.vertical, 4)
            .background(tone == .amber ? Stitch.tintAmber : tone == .danger ? Stitch.dangerBg : Stitch.glassSurface2, in: Capsule())
            .overlay(Capsule().strokeBorder(Stitch.glassStroke))
    }
}

/// S/Notice: inline callout with an icon. Info = boundary statement, warn = attention, danger = error.
public struct StitchNotice: View {
    let title: String
    let text: String
    let tone: StitchTone
    public init(_ title: String, body: String, tone: StitchTone = .default) {
        self.title = title; self.text = body; self.tone = tone
    }
    public var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: tone == .warn ? "exclamationmark.triangle.fill" : tone == .danger ? "xmark.octagon.fill" : "info.circle")
                .foregroundStyle(tone == .warn ? Stitch.warnPrimary : tone == .danger ? Stitch.dangerPrimary : Stitch.textPrimary)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).stitch(.bodyMedium13)
                    .foregroundStyle(tone == .warn ? Stitch.warnPrimary : tone == .danger ? Stitch.dangerPrimary : Stitch.textPrimary)
                Text(text).stitch(.body13).foregroundStyle(Stitch.textSecondary)
            }
            Spacer(minLength: 0)
        }
        .padding(12).glass(radius: 8, fill: Stitch.glassInset)
    }
}

/// S/Button styles. Primary = the one main action, secondary = neutral, destructive = danger, link = text.
public struct StitchButtonStyle: ButtonStyle {
    public enum Kind { case primary, secondary, destructive, link }
    let kind: Kind
    let compact: Bool
    @Environment(\.isEnabled) private var isEnabled
    /// - Parameter compact: chip-sized label (Inter Medium 13) instead of the display label.
    public init(_ kind: Kind = .primary, compact: Bool = false) { self.kind = kind; self.compact = compact }
    public func makeBody(configuration: Configuration) -> some View {
        let shape = RoundedRectangle(cornerRadius: 8, style: .continuous)
        configuration.label
            .stitch(compact ? .bodyMedium13 : .displayH3)
            .lineLimit(2).multilineTextAlignment(.center).minimumScaleFactor(0.8)
            .foregroundStyle(foreground)
            .padding(.horizontal, 16)
            .frame(maxWidth: .infinity, minHeight: kind == .link ? 40 : 48)
            .background(background, in: shape)
            .overlay { if kind == .secondary || kind == .destructive || !isEnabled { shape.strokeBorder(Stitch.glassStroke) } }
            .shadow(color: kind == .primary && isEnabled ? Stitch.accentSoft.opacity(0.35) : .clear, radius: 9, y: 6)
            .opacity(configuration.isPressed ? 0.8 : 1)
            .contentShape(shape)
    }
    private var foreground: Color {
        guard isEnabled else { return Stitch.textDisabled }
        switch kind {
        case .primary: return Stitch.accentOn
        case .secondary: return Stitch.textPrimary
        case .destructive: return Stitch.dangerPrimary
        case .link: return Stitch.accentPrimary
        }
    }
    private var background: Color {
        guard isEnabled else { return kind == .link ? .clear : Stitch.glassSurface }
        switch kind {
        case .primary: return Stitch.accentPrimary
        case .secondary: return Stitch.glassSurface2
        case .destructive: return Stitch.dangerBg
        case .link: return .clear
        }
    }
}

extension ButtonStyle where Self == StitchButtonStyle {
    public static func stitch(_ kind: StitchButtonStyle.Kind = .primary, compact: Bool = false) -> StitchButtonStyle {
        StitchButtonStyle(kind, compact: compact)
    }
}

/// S/Field: a labelled form row — mono label, mono value, and a trailing control.
public struct StitchField<Trailing: View>: View {
    let label: String
    let value: String
    let trailing: Trailing
    public init(_ label: String, value: String, @ViewBuilder trailing: () -> Trailing) {
        self.label = label; self.value = value; self.trailing = trailing()
    }
    public var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(label).stitch(.monoLabel).textCase(.uppercase).foregroundStyle(Stitch.textMuted)
                if !value.isEmpty { Text(value).stitch(.monoBody).foregroundStyle(Stitch.textPrimary) }
            }
            Spacer(minLength: 0)
            trailing
        }
        .padding(.horizontal, 16).padding(.vertical, 14)
        .glass(radius: 8)
        .accessibilityElement(children: .combine)
    }
}

extension StitchField where Trailing == EmptyView {
    public init(_ label: String, value: String) { self.init(label, value: value) { EmptyView() } }
}

/// S/Field (Toggle): the value line says what the switch means in words.
public struct StitchToggleField: View {
    let label: String
    let onText: String
    let offText: String
    @Binding var isOn: Bool
    public init(_ label: String, isOn: Binding<Bool>, on: String = "On", off: String = "Off") {
        self.label = label; self._isOn = isOn; self.onText = on; self.offText = off
    }
    public var body: some View {
        StitchField(label, value: isOn ? onText : offText) {
            Toggle(label, isOn: $isOn).labelsHidden().tint(Stitch.accentPrimary)
        }
    }
}

/// The − / + pair used by S/Field (Stepper).
public struct StitchStepperButtons: View {
    let decrement: () -> Void
    let increment: () -> Void
    public init(decrement: @escaping () -> Void, increment: @escaping () -> Void) {
        self.decrement = decrement; self.increment = increment
    }
    public var body: some View {
        HStack(spacing: 8) {
            stepButton("−", label: "Decrease", action: decrement)
            stepButton("+", label: "Increase", action: increment)
        }
    }
    private func stepButton(_ glyph: String, label: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(glyph).stitch(.monoBodyBold).foregroundStyle(Stitch.textPrimary)
                .frame(width: 36, height: 32)
                .background(Stitch.glassSurface2, in: RoundedRectangle(cornerRadius: 6, style: .continuous))
        }
        .buttonStyle(.plain).accessibilityLabel(label)
    }
}

/// S/KeyValue: label left, mono value right.
public struct StitchKeyValue: View {
    let label: String
    let value: String
    public init(_ label: String, value: String) { self.label = label; self.value = value }
    public var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            Text(label).stitch(.body15).foregroundStyle(Stitch.textSecondary)
            Spacer(minLength: 8)
            Text(value).stitch(.monoBody).foregroundStyle(Stitch.textPrimary).multilineTextAlignment(.trailing)
        }
        .padding(.vertical, 8)
        .accessibilityElement(children: .combine)
    }
}

/// S/ListRow: leading symbol, title, subtitle and a chevron. Use as a NavigationLink or Button label.
public struct StitchListRow: View {
    let symbol: String
    let title: String
    let subtitle: String
    let chevron: Bool
    public init(_ title: String, subtitle: String, symbol: String, chevron: Bool = true) {
        self.title = title; self.subtitle = subtitle; self.symbol = symbol; self.chevron = chevron
    }
    public var body: some View {
        HStack(spacing: 12) {
            Image(systemName: symbol).foregroundStyle(Stitch.accentPrimary).frame(width: 24)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).stitch(.bodyMedium15).foregroundStyle(Stitch.textPrimary)
                Text(subtitle).stitch(.bodyMedium12).foregroundStyle(Stitch.textMuted)
            }
            Spacer(minLength: 0)
            if chevron { Image(systemName: "chevron.right").foregroundStyle(Stitch.textMuted) }
        }
        .multilineTextAlignment(.leading)
        .padding(.horizontal, 16).padding(.vertical, 14)
        .glass(radius: 8)
        .contentShape(Rectangle())
    }
}

/// S/Stat: large numeral with a unit and a mono label.
public struct StitchStat: View {
    let label: String
    let value: String
    let unit: String
    public init(_ label: String, value: String, unit: String) { self.label = label; self.value = value; self.unit = unit }
    public var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).stitch(.monoLabel).textCase(.uppercase).foregroundStyle(Stitch.textMuted)
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text(value).stitch(.monoNumberLarge).foregroundStyle(Stitch.textPrimary)
                Text(unit).stitch(.monoBody).foregroundStyle(Stitch.textMuted)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}

/// S/Timer: rest (or paused) state, mm:ss monospaced.
public struct StitchTimer: View {
    let label: String
    let value: String
    let caption: String
    public init(_ label: String, value: String, caption: String) { self.label = label; self.value = value; self.caption = caption }
    public var body: some View {
        VStack(spacing: 6) {
            Text(label).stitch(.monoLabel).textCase(.uppercase).foregroundStyle(Stitch.textMuted)
            Text(value).stitch(.monoNumberLarge).foregroundStyle(Stitch.textPrimary).monospacedDigit()
            Text(caption).stitch(.body13).foregroundStyle(Stitch.textSecondary)
        }
        .frame(maxWidth: .infinity).padding(.vertical, 20).padding(.horizontal, 16)
        .glass(.accent)
        .accessibilityElement(children: .combine)
    }
}

/// S/SetRow (Logged): checkmark, set number, what happened, and the RIR chip.
public struct StitchLoggedSet: View {
    let index: Int
    let result: String
    let rir: String
    public init(index: Int, result: String, rir: String) { self.index = index; self.result = result; self.rir = rir }
    public var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "checkmark.circle.fill").foregroundStyle(Stitch.accentPrimary)
            Text("\(index)").stitch(.monoBodyBold).foregroundStyle(Stitch.textPrimary)
            Text(result).stitch(.monoBody).foregroundStyle(Stitch.textPrimary)
            Spacer(minLength: 0)
            Text(rir).stitch(.monoSmall).foregroundStyle(Stitch.textPrimary)
                .padding(.horizontal, 6).padding(.vertical, 2)
                .background(Stitch.glassSurface2, in: RoundedRectangle(cornerRadius: 4))
        }
        .padding(.horizontal, 14).padding(.vertical, 12)
        .glass(radius: 8, fill: Stitch.glassInset)
        .accessibilityElement(children: .combine)
    }
}

/// S/Header (Root): breadcrumb, preview pill and large title over glass chrome.
public struct StitchRootHeader: View {
    let title: String
    let pill: String?
    let pillTone: StitchPill.Tone
    let onPill: () -> Void
    public init(_ title: String, pill: String?, pillTone: StitchPill.Tone = .amber, onPill: @escaping () -> Void = {}) {
        self.title = title; self.pill = pill; self.pillTone = pillTone; self.onPill = onPill
    }
    public var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 6) {
                Text("AI Trainer").foregroundStyle(Stitch.textPrimary)
                Text("/").foregroundStyle(Stitch.textMuted)
                Text(title).foregroundStyle(Stitch.textMuted)
                Spacer(minLength: 8)
                if let pill {
                    Button(action: onPill) { StitchPill(pill, tone: pillTone).minimumScaleFactor(0.75) }.buttonStyle(.plain)
                        .layoutPriority(1)
                        .accessibilityHint("Explains the preview build")
                }
            }
            .stitch(.displayH3).lineLimit(1)
            Text(title).stitch(.displayTitle).foregroundStyle(Stitch.textPrimary).accessibilityAddTraits(.isHeader)
        }
        .padding(.horizontal, 16).padding(.top, 4).padding(.bottom, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background {
            ZStack { Rectangle().fill(.ultraThinMaterial); Stitch.glassChrome }.ignoresSafeArea(edges: .top)
        }
        .overlay(alignment: .bottom) { Stitch.strokeHairline.frame(height: 1) }
    }
}

/// S/Header (Sheet): title and Cancel above a hairline. The system supplies the grabber.
public struct StitchSheetHeader: View {
    let title: String
    let onCancel: () -> Void
    public init(_ title: String, onCancel: @escaping () -> Void) { self.title = title; self.onCancel = onCancel }
    public var body: some View {
        HStack {
            Text(title).stitch(.displayH2).foregroundStyle(Stitch.textPrimary).accessibilityAddTraits(.isHeader)
            Spacer()
            Button("Cancel", action: onCancel).stitch(.bodyMedium15).foregroundStyle(Stitch.accentPrimary)
        }
        .padding(.horizontal, 16).padding(.top, 20).padding(.bottom, 12)
        .overlay(alignment: .bottom) { Stitch.strokeHairline.frame(height: 1) }
    }
}

/// Muted footnote text used under fields and buttons.
public struct StitchFootnote: View {
    let text: String
    public init(_ text: String) { self.text = text }
    public var body: some View {
        Text(text).stitch(.body13).foregroundStyle(Stitch.textMuted).frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Layout helpers

extension View {
    /// The standard scroll column: 16 pt gutters, 12 pt spacing, over the backdrop.
    public func stitchScrollColumn() -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) { self }
                .padding(.horizontal, 16).padding(.top, 12).padding(.bottom, 32)
        }
        .scrollIndicators(.hidden)
        .background { StitchBackdrop() }
    }

    /// Presents content as a Stitch sheet: glass background, header with Cancel, scrolling body.
    public func stitchSheet(_ title: String, onCancel: @escaping () -> Void) -> some View {
        VStack(spacing: 0) {
            StitchSheetHeader(title, onCancel: onCancel)
            ScrollView {
                VStack(alignment: .leading, spacing: 12) { self }
                    .padding(.horizontal, 16).padding(.top, 12).padding(.bottom, 32)
            }
            .scrollDismissesKeyboard(.interactively)
        }
        .background { StitchBackdrop().opacity(0.9) }
        .presentationDragIndicator(.visible)
        .presentationBackground(Stitch.glassSheet)
        .presentationCornerRadius(28)
        .preferredColorScheme(.dark)
    }
}
