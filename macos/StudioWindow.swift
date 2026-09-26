import Cocoa
import WebKit

/// Native window for Hindi Reel Studio. The process stays alive so the
/// bundle icon remains in the Dock instead of handing off to a browser.
///
/// Supports two launch modes:
///   1. **Standalone (frozen)** — runs the PyInstaller-bundled runtime
///      from Contents/Resources/runtime/run_standalone
///   2. **Development (venv)** — runs .venv/bin/streamlit from the
///      project directory (fallback when frozen runtime is absent)
///
/// Network & IP support:
///   - Dual-stack localhost, IPv4 (127.0.0.1), and IPv6 ([::1])
///   - Port and window title are read from Info.plist so the same code
///     serves both Release (port 8501) and Dev (port 8502) variants.
final class StudioApp: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    private var window: NSWindow!
    private var webView: WKWebView!
    private var server: Process?

    /// Server port — read from Info.plist "HRSServerPort" key, default 8501
    private let port: Int = {
        if let p = Bundle.main.object(forInfoDictionaryKey: "HRSServerPort") as? Int, p > 0 {
            return p
        }
        return 8501
    }()

    /// Server host — read from Info.plist "HRSServerHost" or HRS_HOST environment variable, default "::1" (IPv6 loopback)
    private let host: String = {
        if let h = ProcessInfo.processInfo.environment["HRS_HOST"], !h.isEmpty {
            return h
        }
        if let h = Bundle.main.object(forInfoDictionaryKey: "HRSServerHost") as? String, !h.isEmpty {
            return h
        }
        return "::1"
    }()

    /// Window title — read from Info.plist "CFBundleDisplayName", fallback to CFBundleName
    private let windowTitle: String = {
        if let name = Bundle.main.object(forInfoDictionaryKey: "CFBundleDisplayName") as? String {
            return name
        }
        if let name = Bundle.main.object(forInfoDictionaryKey: "CFBundleName") as? String {
            return name
        }
        return "Hindi Reel Studio"
    }()

    /// Project directory — parent of the .app bundle
    private let projectDir: String = {
        (Bundle.main.bundlePath as NSString).deletingLastPathComponent
    }()

    override init() {
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
        window.title = windowTitle
        window.titlebarAppearsTransparent = false
        window.minSize = NSSize(width: 900, height: 640)
        window.center()
        window.setFrameAutosaveName("HindiReelStudio_\(port)")

        let config = WKWebViewConfiguration()
        webView = WKWebView(frame: window.contentView!.bounds, configuration: config)
        webView.autoresizingMask = [.width, .height]
        webView.navigationDelegate = self
        window.contentView?.addSubview(webView)
        window.makeKeyAndOrderFront(nil)
    }

    /// Candidate URLs supporting IPv6 loopback ([::1]), IPv4 (127.0.0.1), and localhost
    private func candidateURLs() -> [URL] {
        var urls: [URL] = []
        let cleanHost = host.trimmingCharacters(in: CharacterSet(charactersIn: "[]"))

        if cleanHost.contains(":") {
            // Explicit IPv6 literal address e.g. ::1
            if let u = URL(string: "http://[\(cleanHost)]:\(port)/") { urls.append(u) }
        } else {
            if let u = URL(string: "http://\(cleanHost):\(port)/") { urls.append(u) }
        }

        // Dual-stack and IPv6/IPv4 fallback probe candidates
        let fallbacks = [
            "http://localhost:\(port)/",
            "http://127.0.0.1:\(port)/",
            "http://[::1]:\(port)/"
        ]
        for fb in fallbacks {
            if let u = URL(string: fb), !urls.contains(u) {
                urls.append(u)
            }
        }
        return urls
    }

    private func startServerIfNeeded() {
        // Probe candidate URLs (IPv4, IPv6, localhost) to see if server is already running
        for probeURL in candidateURLs() {
            if let _ = try? Data(contentsOf: probeURL) {
                return
            }
        }

        // --- Try frozen runtime first (standalone .app) ---
        let frozenRuntime = (Bundle.main.resourcePath ?? "") + "/runtime/run_standalone"
        if FileManager.default.isExecutableFile(atPath: frozenRuntime) {
            launchFrozenRuntime(executable: frozenRuntime)
            return
        }

        // --- Fallback to .venv/bin/streamlit (development mode) ---
        let streamlit = (projectDir as NSString).appendingPathComponent(".venv/bin/streamlit")
        let appPy = (projectDir as NSString).appendingPathComponent("app.py")
        guard FileManager.default.isExecutableFile(atPath: streamlit) else { return }

        let cleanHost = host.trimmingCharacters(in: CharacterSet(charactersIn: "[]"))
        let process = Process()
        process.executableURL = URL(fileURLWithPath: streamlit)
        process.arguments = [
            "run", appPy,
            "--global.developmentMode=false",
            "--server.headless=true",
            "--server.address=\(cleanHost)",
            "--server.port=\(port)",
        ]
        process.currentDirectoryURL = URL(fileURLWithPath: projectDir)

        var env = ProcessInfo.processInfo.environment
        env["HRS_PORT"] = String(port)
        env["HRS_HOST"] = cleanHost
        env["STREAMLIT_SERVER_ADDRESS"] = cleanHost
        env["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
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

        configureLogging(process: process)
        try? process.run()
        server = process
    }

    /// Launch the PyInstaller-frozen runtime binary
    private func launchFrozenRuntime(executable: String) {
        let cleanHost = host.trimmingCharacters(in: CharacterSet(charactersIn: "[]"))
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = []

        var env = ProcessInfo.processInfo.environment
        env["HRS_PORT"] = String(port)
        env["HRS_HOST"] = cleanHost
        env["STREAMLIT_SERVER_ADDRESS"] = cleanHost
        env["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
        process.environment = env
        
        let runDir = (Bundle.main.resourcePath ?? "") + "/runtime"
        process.currentDirectoryURL = URL(fileURLWithPath: runDir)

        configureLogging(process: process)
        try? process.run()
        server = process
    }

    /// Set up log file for the server process (safe for read-only /Applications)
    private func configureLogging(process: Process) {
        var logURL: URL? = nil
        let localCandidate = URL(fileURLWithPath: (projectDir as NSString).appendingPathComponent(".server_\(port).log"))
        
        if FileManager.default.isWritableFile(atPath: projectDir) {
            logURL = localCandidate
        } else {
            if let userLogs = FileManager.default.urls(for: .libraryDirectory, in: .userDomainMask).first?.appendingPathComponent("Logs/HindiReelStudio") {
                try? FileManager.default.createDirectory(at: userLogs, withIntermediateDirectories: true)
                logURL = userLogs.appendingPathComponent("server_\(port).log")
            } else {
                logURL = URL(fileURLWithPath: "/tmp/hindi_reel_studio_\(port).log")
            }
        }

        if let logURL {
            if !FileManager.default.fileExists(atPath: logURL.path) {
                FileManager.default.createFile(atPath: logURL.path, contents: nil)
            }
            if let handle = try? FileHandle(forWritingTo: logURL) {
                process.standardOutput = handle
                process.standardError = handle
            }
        }
        process.standardInput = FileHandle.nullDevice
    }

    private func waitThenLoad() {
        let urls = candidateURLs()
        DispatchQueue.global(qos: .userInitiated).async {
            var activeURL: URL? = nil
            for _ in 0..<60 {
                for candidate in urls {
                    if let _ = try? Data(contentsOf: candidate) {
                        activeURL = candidate
                        break
                    }
                }
                if activeURL != nil { break }
                Thread.sleep(forTimeInterval: 0.5)
            }
            let targetURL = activeURL ?? urls.first ?? URL(string: "http://localhost:\(self.port)/")!
            DispatchQueue.main.async {
                self.webView.load(URLRequest(url: targetURL))
            }
        }
    }
}

let app = NSApplication.shared
let delegate = StudioApp()
app.delegate = delegate
app.run()
