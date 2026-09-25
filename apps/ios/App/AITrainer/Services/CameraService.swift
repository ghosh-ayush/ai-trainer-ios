import AVFoundation
import SwiftUI
import AITrainerCore

/// Camera frames are processed transiently on a serial queue; no video is recorded or uploaded.
final class CameraService: NSObject, ObservableObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    let session = AVCaptureSession()
    private let queue = DispatchQueue(label: "ai.trainer.pose", qos: .userInitiated)
    private var configured = false
    private let intentLock = NSLock()
    private var wantsRunning = false
    private var shouldRun: Bool { intentLock.lock(); defer { intentLock.unlock() }; return wantsRunning }
    private let counter = CameraRepTracker()
    private var benchmark = Benchmark()
    private var startedAt = Date()
    @Published private(set) var running = false
    @Published private(set) var message = "Camera is off"
    @Published private(set) var observation = RepObservation()
    @Published private(set) var p50 = 0.0
    @Published private(set) var p95 = 0.0
    @Published private(set) var processedFPS = 0.0
    @Published private(set) var frameCount = 0
    @Published private(set) var modelRevision = 0
    /// The camera in use once configured; the preview uses it to keep the image level (see `PreviewView`).
    @Published private(set) var activeDevice: AVCaptureDevice?

    func start() {
        intentLock.lock(); wantsRunning = true; intentLock.unlock()
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: configureAndStart()
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                if granted { self?.configureAndStart() }
                else { self?.publish("Camera access was not granted. P1 manual training still works.") }
            }
        default: publish("Camera unavailable or access denied. Review Camera permission in iOS Settings.")
        }
    }
    private func configureAndStart() {
        queue.async { [weak self] in
            guard let self, self.shouldRun else { return }
            do {
                if !self.configured {
                    guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .front) else {
                        throw TrainerError.invalid("No camera is available. Use a physical iPhone for this experiment.")
                    }
                    let input = try AVCaptureDeviceInput(device: device)
                    let output = AVCaptureVideoDataOutput()
                    output.alwaysDiscardsLateVideoFrames = true
                    output.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
                    output.setSampleBufferDelegate(self, queue: self.queue)
                    self.session.beginConfiguration()
                    if self.session.canSetSessionPreset(.vga640x480) { self.session.sessionPreset = .vga640x480 }
                    guard self.session.canAddInput(input), self.session.canAddOutput(output) else {
                        self.session.commitConfiguration(); throw TrainerError.invalid("Camera configuration is unsupported.")
                    }
                    self.session.addInput(input); self.session.addOutput(output)
                    self.session.commitConfiguration(); self.configured = true
                    DispatchQueue.main.async { self.activeDevice = device }
                }
                self.counter.reset(); self.benchmark = Benchmark(); self.startedAt = Date()
                guard self.shouldRun else { return }
                self.session.startRunning()
                DispatchQueue.main.async { self.running = true; self.message = "One person, portrait phone, right shoulder/elbow/wrist visible" }
            } catch { self.publish(error.localizedDescription) }
        }
    }
    func stop() {
        intentLock.lock(); wantsRunning = false; intentLock.unlock()
        queue.async { [weak self] in
            guard let self else { return }
            if self.session.isRunning { self.session.stopRunning() }
            self.counter.reset()
            DispatchQueue.main.async { self.running = false; self.message = "Camera stopped. No video was stored." }
        }
    }
    func resetCount() {
        queue.async { [weak self] in
            guard let self else { return }; self.counter.reset()
            let value = self.counter.observation
            DispatchQueue.main.async { self.observation = value }
        }
    }
    /// Turns the frames the rep counter reads so they stay level with the horizon, however the phone
    /// is held. The angle comes from the device's rotation coordinator (see `PreviewView`).
    func setCaptureRotation(_ angle: CGFloat) {
        queue.async { [weak self] in
            guard let self, let connection = self.session.outputs.first?.connection(with: .video),
                  connection.isVideoRotationAngleSupported(angle) else { return }
            connection.videoRotationAngle = angle
        }
    }
    private func publish(_ message: String) { DispatchQueue.main.async { self.message = message } }
    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        autoreleasepool {
            guard let buffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
            let start = Date(), timestamp = CMSampleBufferGetPresentationTimeStamp(sampleBuffer).seconds
            let result = counter.process(buffer, timestamp: timestamp)
            let revision = counter.modelRevision
            benchmark.record(milliseconds: Date().timeIntervalSince(start) * 1000)
            let count = benchmark.processedFrames
            let median = benchmark.percentile(0.5) ?? 0, tail = benchmark.percentile(0.95) ?? 0
            let fps = Double(count) / max(0.001, Date().timeIntervalSince(startedAt))
            DispatchQueue.main.async {
                self.observation = result; self.p50 = median; self.p95 = tail
                self.processedFPS = fps; self.frameCount = count; self.modelRevision = revision
            }
        }
    }
}
/// The live camera image. It stays level with the horizon as the phone turns: Apple's rotation
/// coordinator reports the angle for the preview and for the frames the rep counter reads, and
/// both are applied whenever it changes. The screen itself stays portrait.
final class PreviewView: UIView {
    override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
    var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    private var coordinator: AVCaptureDevice.RotationCoordinator?
    private var observations: [NSKeyValueObservation] = []
    private weak var attachedDevice: AVCaptureDevice?

    /// Starts following `device`'s orientation. Calling it again for the same device does nothing.
    func follow(_ device: AVCaptureDevice, onCaptureAngle: @escaping (CGFloat) -> Void) {
        guard attachedDevice !== device else { return }
        attachedDevice = device
        observations.removeAll()
        let coordinator = AVCaptureDevice.RotationCoordinator(device: device, previewLayer: previewLayer)
        self.coordinator = coordinator
        observations.append(coordinator.observe(\.videoRotationAngleForHorizonLevelPreview, options: [.initial, .new]) { [weak self] coordinator, _ in
            let angle = coordinator.videoRotationAngleForHorizonLevelPreview
            DispatchQueue.main.async { self?.applyPreviewAngle(angle) }
        })
        observations.append(coordinator.observe(\.videoRotationAngleForHorizonLevelCapture, options: [.initial, .new]) { coordinator, _ in
            onCaptureAngle(coordinator.videoRotationAngleForHorizonLevelCapture)
        })
    }
    override func layoutSubviews() {
        super.layoutSubviews()
        if let coordinator { applyPreviewAngle(coordinator.videoRotationAngleForHorizonLevelPreview) }
    }
    private func applyPreviewAngle(_ angle: CGFloat) {
        guard let connection = previewLayer.connection, connection.isVideoRotationAngleSupported(angle) else { return }
        connection.videoRotationAngle = angle
    }
}
struct CameraPreview: UIViewRepresentable {
    @ObservedObject var camera: CameraService
    func makeUIView(context: Context) -> PreviewView {
        let view = PreviewView()
        view.previewLayer.session = camera.session
        view.previewLayer.videoGravity = .resizeAspectFill
        return view
    }
    func updateUIView(_ uiView: PreviewView, context: Context) {
        guard let device = camera.activeDevice else { return }
        let camera = camera
        uiView.follow(device) { angle in camera.setCaptureRotation(angle) }
    }
}
