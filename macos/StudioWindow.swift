import Cocoa
import WebKit

/// Native window for Hindi Reel Studio. The process stays alive so the
/// bundle icon remains in the Dock instead of handing off to a browser.
final class StudioApp: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    private var window: NSWindow!
    private var webView: WKWebView!
    private var server: Process?
    private let port = 8501
    private let projectDir: String

    override init() {
        let bundle = Bundle.main.bundlePath
        // Hindi Reel Studio.app lives in the project root.
        projectDir = (bundle as NSString).deletingLastPathComponent
        super.init()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        buildWindow()
        startServerIfNeeded()
        waitThenLoad()
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    func applicationWillTerminate(_ notification: Notification) {
        if let server, server.isRunning {
            server.terminate()
        }
    }

    private func buildWindow() {
        let screen = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1280, height: 860)
        let width = min(1280, screen.width * 0.9)
        let height = min(860, screen.height * 0.9)
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: width, height: height),
            styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        window.title = "Hindi Reel Studio"
        window.titlebarAppearsTransparent = false
        window.minSize = NSSize(width: 900, height: 640)
        window.center()
        window.setFrameAutosaveName("HindiReelStudio")

        let config = WKWebViewConfiguration()
        webView = WKWebView(frame: window.contentView!.bounds, configuration: config)
        webView.autoresizingMask = [.width, .height]
        webView.navigationDelegate = self
        window.contentView?.addSubview(webView)
        window.makeKeyAndOrderFront(nil)
    }

    private func startServerIfNeeded() {
        let probe = "http://127.0.0.1:\(port)/"
        if let url = URL(string: probe),
           let _ = try? Data(contentsOf: url) {
            return
        }
        let streamlit = (projectDir as NSString).appendingPathComponent(".venv/bin/streamlit")
        let app = (projectDir as NSString).appendingPathComponent("app.py")
        guard FileManager.default.isExecutableFile(atPath: streamlit) else { return }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: streamlit)
        process.arguments = [
            "run", app,
            "--server.headless", "true",
            "--server.address", "127.0.0.1",
            "--server.port", String(port),
        ]
        process.currentDirectoryURL = URL(fileURLWithPath: projectDir)

        var env = ProcessInfo.processInfo.environment
        let extraPaths = [
            "/opt/homebrew/bin",
            "/opt/homebrew/sbin",
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
            "/usr/sbin",
            "/sbin",
            NSHomeDirectory().appending("/.gemini/antigravity-cli/bin")
        ]
        let currentPath = env["PATH"] ?? ""
        var pathComponents = currentPath.split(separator: ":").map(String.init)
        for p in extraPaths {
            if !pathComponents.contains(p) && FileManager.default.fileExists(atPath: p) {
                pathComponents.append(p)
            }
        }
        env["PATH"] = pathComponents.joined(separator: ":")
        process.environment = env

        let logURL = URL(fileURLWithPath: (projectDir as NSString).appendingPathComponent(".server.log"))
        FileManager.default.createFile(atPath: logURL.path, contents: nil)
        if let handle = try? FileHandle(forWritingTo: logURL) {
            process.standardOutput = handle
            process.standardError = handle
        }
        process.standardInput = FileHandle.nullDevice
        try? process.run()
        server = process
    }

    private func waitThenLoad() {
        let url = URL(string: "http://127.0.0.1:\(port)/")!
        DispatchQueue.global(qos: .userInitiated).async {
            for _ in 0..<40 {
                if let _ = try? Data(contentsOf: url) { break }
                Thread.sleep(forTimeInterval: 0.4)
            }
            DispatchQueue.main.async {
                self.webView.load(URLRequest(url: url))
            }
        }
    }
}

let app = NSApplication.shared
let delegate = StudioApp()
app.delegate = delegate
app.run()
