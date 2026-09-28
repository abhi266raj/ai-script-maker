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
    private let serverQueue = DispatchQueue(label: "com.hindireel.studio.server")
    private var startItem: NSMenuItem?
    private var stopItem: NSMenuItem?
    private var restartItem: NSMenuItem?

    /// Server port — read from Info.plist "HRSServerPort" key, default 8501
    private let port: Int = {
        if let p = Bundle.main.object(forInfoDictionaryKey: "HRSServerPort") as? Int, p > 0 {
            return p
        }
        return 8501
    }()

    /// Server host — read from Info.plist "HRSServerHost" or HRS_HOST environment variable, default "::" (dual-stack IPv6 + IPv4)
    private let host: String = {
        if let h = ProcessInfo.processInfo.environment["HRS_HOST"], !h.isEmpty {
            return h
        }
        if let h = Bundle.main.object(forInfoDictionaryKey: "HRSServerHost") as? String, !h.isEmpty {
            return h
        }
        return "::"
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
        buildServerMenu()
        // Packaged and dev launches both boot the server off the main thread.
        serverQueue.async { self.startServer(reload: true) }
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
        installToolbar()
    }

    private func installToolbar() {
        let toolbar = NSToolbar(identifier: "HindiReelStudioServer")
        toolbar.delegate = self
        toolbar.displayMode = .iconAndLabel
        window.toolbar = toolbar
    }

    private func buildServerMenu() {
        let serverMenu = NSMenu(title: "Server")
        let start = NSMenuItem(title: "Start Server", action: #selector(startServerAction), keyEquivalent: "r")
        start.keyEquivalentModifierMask = [.command]
        start.target = self
        let stop = NSMenuItem(title: "Stop Server", action: #selector(stopServerAction), keyEquivalent: ".")
        stop.keyEquivalentModifierMask = [.command]
        stop.target = self
        let restart = NSMenuItem(title: "Restart Server", action: #selector(restartServerAction), keyEquivalent: "r")
        restart.keyEquivalentModifierMask = [.command, .shift]
        restart.target = self
        serverMenu.addItem(start)
        serverMenu.addItem(stop)
        serverMenu.addItem(restart)
        startItem = start
        stopItem = stop
        restartItem = restart

        let top = NSMenuItem(title: "Server", action: nil, keyEquivalent: "")
        top.submenu = serverMenu
        NSApp.mainMenu?.addItem(top)
        refreshServerControls()
    }

    @objc private func startServerAction() {
        serverQueue.async { self.startServer(reload: true) }
    }

    @objc private func stopServerAction() {
        serverQueue.async {
            self.stopServer()
            DispatchQueue.main.async { self.setStatus("Server stopped") }
        }
    }

    @objc private func restartServerAction() {
        serverQueue.async {
            self.stopServer()
            Thread.sleep(forTimeInterval: 0.4)
            self.startServer(reload: true)
        }
    }

    private func setStatus(_ text: String) {
        window.title = "\(windowTitle) — \(text)"
        refreshServerControls()
    }

    private func refreshServerControls() {
        let running = serverIsRunning()
        startItem?.isEnabled = !running
        stopItem?.isEnabled = running
        restartItem?.isEnabled = true
        window.toolbar?.validateVisibleItems()
    }

    private func serverIsRunning() -> Bool {
        if let server, server.isRunning { return true }
        return probeServer(timeout: 0.4) != nil
    }

    /// Candidate URLs supporting IPv6 loopback ([::1]), IPv4 (127.0.0.1), and localhost
    private func candidateURLs() -> [URL] {
        var urls: [URL] = []
        let cleanHost = host.trimmingCharacters(in: CharacterSet(charactersIn: "[]"))

        if cleanHost == "::" || cleanHost.isEmpty || cleanHost == "localhost" {
            // Dual-stack: both IPv6 and IPv4 loopback are active
            let dualStackEndpoints = [
                "http://[::1]:\(port)/",
                "http://127.0.0.1:\(port)/",
                "http://localhost:\(port)/"
            ]
            for ep in dualStackEndpoints {
                if let u = URL(string: ep), !urls.contains(u) { urls.append(u) }
            }
        } else if cleanHost.contains(":") {
            // Explicit IPv6 literal address e.g. ::1
            if let u = URL(string: "http://[\(cleanHost)]:\(port)/") { urls.append(u) }
        } else {
            // Explicit IPv4 or hostname
            if let u = URL(string: "http://\(cleanHost):\(port)/") { urls.append(u) }
        }

        // Dual-stack and IPv6/IPv4 fallback probe candidates
        let fallbacks = [
            "http://[::1]:\(port)/",
            "http://127.0.0.1:\(port)/",
            "http://localhost:\(port)/"
        ]
        for fb in fallbacks {
            if let u = URL(string: fb), !urls.contains(u) {
                urls.append(u)
            }
        }
        return urls
    }

    /// Start the studio server in the background. Safe to call when it is already up.
    private func startServer(reload: Bool) {
        if probeServer(timeout: 0.6) != nil {
            DispatchQueue.main.async {
                self.setStatus("Server running")
                if reload { self.waitThenLoad() }
            }
            return
        }

        DispatchQueue.main.async { self.setStatus("Starting server…") }

        // --- Try frozen runtime first (standalone .app) ---
        let frozenRuntime = (Bundle.main.resourcePath ?? "") + "/runtime/run_standalone"
        if FileManager.default.isExecutableFile(atPath: frozenRuntime) {
            launchFrozenRuntime(executable: frozenRuntime)
            if reload {
                DispatchQueue.main.async { self.waitThenLoad() }
            }
            return
        }

        // --- Fallback to .venv/bin/streamlit (development mode) ---
        let streamlit = (projectDir as NSString).appendingPathComponent(".venv/bin/streamlit")
        let appPy = (projectDir as NSString).appendingPathComponent("app.py")
        guard FileManager.default.isExecutableFile(atPath: streamlit) else {
            appendLog("No packaged runtime at \(frozenRuntime) and no \(streamlit)\n")
            DispatchQueue.main.async { self.setStatus("Server failed to start") }
            return
        }

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

        process.environment = studioEnvironment(host: cleanHost)

        configureLogging(process: process)
        launch(process, label: "development server")
        if reload {
            DispatchQueue.main.async { self.waitThenLoad() }
        }
    }

    /// Launch the PyInstaller-frozen runtime binary
    private func launchFrozenRuntime(executable: String) {
        let cleanHost = host.trimmingCharacters(in: CharacterSet(charactersIn: "[]"))
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = []

        process.environment = studioEnvironment(host: cleanHost)
        
        let runDir = (Bundle.main.resourcePath ?? "") + "/runtime"
        process.currentDirectoryURL = URL(fileURLWithPath: runDir)

        configureLogging(process: process)
        launch(process, label: "packaged server")
    }

    /// PATH inside a double-clicked .app is minimal. Keep Homebrew CLIs reachable.
    private func studioEnvironment(host: String) -> [String: String] {
        var env = ProcessInfo.processInfo.environment
        env["HRS_PORT"] = String(port)
        env["HRS_HOST"] = host
        env["STREAMLIT_SERVER_ADDRESS"] = host
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
        var pathComponents = (env["PATH"] ?? "").split(separator: ":").map(String.init)
        for p in extraPaths where !pathComponents.contains(p) && FileManager.default.fileExists(atPath: p) {
            pathComponents.append(p)
        }
        env["PATH"] = pathComponents.joined(separator: ":")
        return env
    }

    /// Spawn the server process without blocking the window. Failures go to the log.
    private func launch(_ process: Process, label: String) {
        do {
            try process.run()
            server = process
            DispatchQueue.main.async { self.setStatus("Server running") }
        } catch {
            appendLog("Failed to launch \(label): \(error.localizedDescription)\n")
            DispatchQueue.main.async { self.setStatus("Server failed to start") }
        }
    }

    private func stopServer() {
        if let server, server.isRunning {
            server.terminate()
            server.waitUntilExit()
        }
        server = nil
        // The frozen runtime can leave a listener if terminate only hits the parent.
        for pid in listenerPIDs() where pid != ProcessInfo.processInfo.processIdentifier {
            kill(pid, SIGTERM)
        }
    }

    private func listenerPIDs() -> [Int32] {
        let lsof = Process()
        lsof.executableURL = URL(fileURLWithPath: "/usr/sbin/lsof")
        lsof.arguments = ["-nP", "-tiTCP:\(port)", "-sTCP:LISTEN"]
        let pipe = Pipe()
        lsof.standardOutput = pipe
        lsof.standardError = FileHandle.nullDevice
        do {
            try lsof.run()
        } catch {
            return []
        }
        lsof.waitUntilExit()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let text = String(data: data, encoding: .utf8) ?? ""
        return text.split(whereSeparator: \.isNewline).compactMap { Int32($0) }
    }

    private func probeServer(timeout: TimeInterval) -> URL? {
        for candidate in candidateURLs() {
            var request = URLRequest(url: candidate)
            request.timeoutInterval = timeout
            let sem = DispatchSemaphore(value: 0)
            var ok = false
            let task = URLSession.shared.dataTask(with: request) { _, response, _ in
                if let http = response as? HTTPURLResponse, (200..<500).contains(http.statusCode) {
                    ok = true
                }
                sem.signal()
            }
            task.resume()
            _ = sem.wait(timeout: .now() + timeout + 0.2)
            if ok { return candidate }
            task.cancel()
        }
        return nil
    }

    private func appendLog(_ message: String) {
        let path = logFileURL().path
        if let data = message.data(using: .utf8), let handle = FileHandle(forWritingAtPath: path) {
            handle.seekToEndOfFile()
            handle.write(data)
            try? handle.close()
        }
    }

    /// Set up log file for the server process (safe for read-only /Applications)
    private func logFileURL() -> URL {
        let localCandidate = URL(fileURLWithPath: (projectDir as NSString).appendingPathComponent(".server_\(port).log"))
        if FileManager.default.isWritableFile(atPath: projectDir) {
            return localCandidate
        }
        if let userLogs = FileManager.default.urls(for: .libraryDirectory, in: .userDomainMask).first?.appendingPathComponent("Logs/HindiReelStudio") {
            try? FileManager.default.createDirectory(at: userLogs, withIntermediateDirectories: true)
            return userLogs.appendingPathComponent("server_\(port).log")
        }
        return URL(fileURLWithPath: "/tmp/hindi_reel_studio_\(port).log")
    }

    private func configureLogging(process: Process) {
        let logURL = logFileURL()

        if !FileManager.default.fileExists(atPath: logURL.path) {
            FileManager.default.createFile(atPath: logURL.path, contents: nil)
        }
        if let handle = try? FileHandle(forWritingTo: logURL) {
            process.standardOutput = handle
            process.standardError = handle
        }
        process.standardInput = FileHandle.nullDevice
    }

    private func waitThenLoad() {
        DispatchQueue.global(qos: .userInitiated).async {
            var activeURL: URL? = nil
            for _ in 0..<60 {
                activeURL = self.probeServer(timeout: 0.5)
                if activeURL != nil { break }
                Thread.sleep(forTimeInterval: 0.5)
            }
            let targetURL = activeURL ?? self.candidateURLs().first ?? URL(string: "http://localhost:\(self.port)/")!
            DispatchQueue.main.async {
                self.webView.load(URLRequest(url: targetURL))
                self.refreshServerControls()
            }
        }
    }
}

extension StudioApp: NSToolbarDelegate {
    func toolbarAllowedItemIdentifiers(_ toolbar: NSToolbar) -> [NSToolbarItem.Identifier] {
        [.init("start"), .init("stop"), .init("restart")]
    }

    func toolbarDefaultItemIdentifiers(_ toolbar: NSToolbar) -> [NSToolbarItem.Identifier] {
        [.init("start"), .init("stop"), .init("restart")]
    }

    func toolbar(_ toolbar: NSToolbar, itemForItemIdentifier itemIdentifier: NSToolbarItem.Identifier, willBeInsertedIntoToolbar flag: Bool) -> NSToolbarItem? {
        let item = NSToolbarItem(itemIdentifier: itemIdentifier)
        switch itemIdentifier.rawValue {
        case "start":
            item.label = "Start"
            item.image = NSImage(systemSymbolName: "play.fill", accessibilityDescription: "Start Server")
            item.action = #selector(startServerAction)
        case "stop":
            item.label = "Stop"
            item.image = NSImage(systemSymbolName: "stop.fill", accessibilityDescription: "Stop Server")
            item.action = #selector(stopServerAction)
        default:
            item.label = "Restart"
            item.image = NSImage(systemSymbolName: "arrow.clockwise", accessibilityDescription: "Restart Server")
            item.action = #selector(restartServerAction)
        }
        item.target = self
        item.isBordered = true
        return item
    }
}

let app = NSApplication.shared
let delegate = StudioApp()
app.delegate = delegate
app.run()
