// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "AITrainerCore",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [.library(name: "AITrainerCore", targets: ["AITrainerCore"])],
    dependencies: [.package(url: "https://github.com/NazarKozak/RepCounterSDK.git", revision: "94aaae70ebf30ad68522e51dd8be24f7cc793ec8")],
    targets: [
        .binaryTarget(name: "Python", path: "apps/ios/Vendor/Python.xcframework"),
        .target(name: "PythonBridge", dependencies: [.target(name: "Python", condition: .when(platforms: [.iOS]))], path: "apps/ios/PythonBridge"),
        .target(name: "AITrainerCore", dependencies: ["PythonBridge", .product(name: "RepCounterSDK", package: "RepCounterSDK")], path: "apps/ios/Sources/AITrainerCore", resources: [.process("Resources")]),
        .testTarget(name: "AITrainerCoreTests", dependencies: ["AITrainerCore"], path: "apps/ios/Tests/AITrainerCoreTests")
    ],
    swiftLanguageModes: [.v5]
)
