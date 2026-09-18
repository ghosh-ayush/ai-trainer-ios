// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "AITrainerCore",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [.library(name: "AITrainerCore", targets: ["AITrainerCore"])],
    targets: [
        .target(name: "AITrainerCore"),
        .testTarget(name: "AITrainerCoreTests", dependencies: ["AITrainerCore"])
    ]
)
