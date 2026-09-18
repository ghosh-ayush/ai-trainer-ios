// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "AITrainerCore",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [.library(name: "AITrainerCore", targets: ["AITrainerCore"])],
    dependencies: [.package(url: "https://github.com/NazarKozak/RepCounterSDK.git", revision: "94aaae70ebf30ad68522e51dd8be24f7cc793ec8")],
    targets: [
        .target(name: "AITrainerCore", dependencies: [.product(name: "RepCounterSDK", package: "RepCounterSDK")], resources: [.process("Resources")]),
        .testTarget(name: "AITrainerCoreTests", dependencies: ["AITrainerCore"])
    ],
    swiftLanguageModes: [.v5]
)
