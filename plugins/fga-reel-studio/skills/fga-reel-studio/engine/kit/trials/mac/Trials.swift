// Trials for Mac: the Trials page in its own window, with its own Dock icon.
// It starts Trials' server when it's off (through the start.sh Reel Kit writes), so there's nothing to turn on.
// Built once by dev/build_trials_mac.py into the Trials binary next to this file; pipeline/trials.py wraps that
// binary in Trials.app on the creator's Mac. Info.plist tells it where the server is (ReelKitURL) and how to start
// it (ReelKitStart).
import AppKit
import WebKit

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate {
  var window: NSWindow!
  var web: WKWebView!
  let info = Bundle.main.infoDictionary ?? [:]
  lazy var home = URL(string: info["ReelKitURL"] as? String ?? "http://127.0.0.1:5180/")!
  lazy var startScript = info["ReelKitStart"] as? String ?? ""
  var starting = false

  func applicationWillFinishLaunching(_ notification: Notification) {
    // trials://start (the "Trials is off" page's button, in a browser or in here) lands here.
    NSAppleEventManager.shared().setEventHandler(
      self, andSelector: #selector(openLink(_:reply:)),
      forEventClass: AEEventClass(kInternetEventClass), andEventID: AEEventID(kAEGetURL))
  }

  func applicationDidFinishLaunching(_ notification: Notification) {
    NSApp.mainMenu = menu()
    let config = WKWebViewConfiguration()
    config.websiteDataStore = .default()   // keeps the theme and anything else the page saves
    web = WKWebView(frame: .zero, configuration: config)
    web.navigationDelegate = self
    web.uiDelegate = self

    window = NSWindow(
      contentRect: NSRect(x: 0, y: 0, width: 1280, height: 820),
      styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
    window.title = "Trials"
    window.minSize = NSSize(width: 720, height: 520)
    window.contentView = web
    window.center()
    window.setFrameAutosaveName("Trials")
    window.makeKeyAndOrderFront(nil)
    NSApp.activate(ignoringOtherApps: true)
    open()
  }

  func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

  func applicationDidBecomeActive(_ notification: Notification) {
    // Back after a restart or a long while: start the server again if it went off.
    guard web != nil, !starting else { return }
    DispatchQueue.global().async {
      if !self.isUp() { DispatchQueue.main.async { self.open() } }
    }
  }

  @objc func openLink(_ event: NSAppleEventDescriptor, reply: NSAppleEventDescriptor) {
    window?.makeKeyAndOrderFront(nil)
    if web != nil { open() }   // before launch finished, applicationDidFinishLaunching opens it
  }

  // MARK: the server

  func isUp() -> Bool {
    var request = URLRequest(url: home.appendingPathComponent("api/zernio/status"))
    request.timeoutInterval = 2
    request.cachePolicy = .reloadIgnoringLocalCacheData
    let done = DispatchSemaphore(value: 0)
    var ok = false
    URLSession.shared.dataTask(with: request) { _, response, _ in
      ok = (response as? HTTPURLResponse)?.statusCode == 200
      done.signal()
    }.resume()
    done.wait()
    return ok
  }

  /// Loads Trials, starting its server first when it's off.
  func open() {
    guard !starting else { return }
    starting = true
    DispatchQueue.global().async {
      var up = self.isUp()
      if !up {
        DispatchQueue.main.async { self.message("Starting Trials…", detail: "") }
        if FileManager.default.fileExists(atPath: self.startScript) {
          let task = Process()
          task.executableURL = URL(fileURLWithPath: "/bin/sh")
          task.arguments = [self.startScript]   // returns once the server answers, or after 30 seconds
          try? task.run()
          task.waitUntilExit()
        }
        up = self.isUp()
      }
      DispatchQueue.main.async {
        self.starting = false
        if up {
          self.web.load(URLRequest(url: self.home))
        } else {
          self.message(
            "Trials didn't start.",
            detail: "Open Claude and type <code>/reel-kit:trials</code>: it starts Trials and fixes whatever stopped it.",
            retry: true)
        }
      }
    }
  }

  func message(_ title: String, detail: String, retry: Bool = false) {
    let button = retry ? "<a href=\"trials://start\">Try again</a>" : ""
    web.loadHTMLString("""
      <!doctype html><meta charset="utf-8"><style>
      :root { color-scheme: light dark; --bg: #f8f8f8; --ink: #222; --ink-2: #6b6b6b; --chip: #ececec; }
      @media (prefers-color-scheme: dark) { :root { --bg: #1f1f1f; --ink: #f0f0f0; --ink-2: #a8a8a8; --chip: #2e2e2e; } }
      html, body { height: 100%; margin: 0; }
      body { display: grid; place-items: center; background: var(--bg); color: var(--ink);
        font: 15px/1.6 -apple-system, system-ui, sans-serif; -webkit-font-smoothing: antialiased; }
      main { max-width: 420px; padding: 16px; text-align: center; }
      h1 { margin: 0; font-size: 22px; font-weight: 600; letter-spacing: -0.02em; }
      p { margin: 8px 0 0; color: var(--ink-2); }
      code { font: 13px ui-monospace, monospace; padding: 1px 5px; border-radius: 5px; background: var(--chip); white-space: nowrap; }
      a { display: inline-block; margin-top: 20px; padding: 8px 16px; border-radius: 8px; background: var(--ink);
        color: var(--bg); text-decoration: none; font-weight: 500; font-size: 14px; }
      </style><main><h1>\(title)</h1><p>\(detail)</p>\(button)</main>
      """, baseURL: nil)
  }

  // MARK: the page

  func webView(
    _ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
    decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
  ) {
    guard let url = action.request.url else { return decisionHandler(.allow) }
    if url.scheme == "trials" {
      decisionHandler(.cancel)
      open()
    } else if url.scheme == "about" || url.scheme == "blob" || url.scheme == "data"
      || (url.host == home.host && url.port == home.port) {
      decisionHandler(.allow)
    } else {
      decisionHandler(.cancel)   // Instagram, Zernio and every other link: the browser
      NSWorkspace.shared.open(url)
    }
  }

  func webView(
    _ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
    for action: WKNavigationAction, windowFeatures: WKWindowFeatures
  ) -> WKWebView? {
    if let url = action.request.url { NSWorkspace.shared.open(url) }   // target="_blank"
    return nil
  }

  func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
    let code = (error as NSError).code
    if code == NSURLErrorCannotConnectToHost || code == NSURLErrorNetworkConnectionLost || code == NSURLErrorTimedOut {
      open()   // the server went off: start it and come back
    }
  }

  func webView(
    _ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo,
    completionHandler: @escaping ([URL]?) -> Void
  ) {
    let panel = NSOpenPanel()
    panel.canChooseFiles = true
    panel.canChooseDirectories = false
    panel.allowsMultipleSelection = parameters.allowsMultipleSelection
    panel.beginSheetModal(for: window) { completionHandler($0 == .OK ? panel.urls : nil) }
  }

  func webView(
    _ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo,
    completionHandler: @escaping () -> Void
  ) {
    let alert = NSAlert()
    alert.messageText = message
    alert.beginSheetModal(for: window) { _ in completionHandler() }
  }

  func webView(
    _ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo,
    completionHandler: @escaping (Bool) -> Void
  ) {
    let alert = NSAlert()
    alert.messageText = message
    alert.addButton(withTitle: "OK")
    alert.addButton(withTitle: "Cancel")
    alert.beginSheetModal(for: window) { completionHandler($0 == .alertFirstButtonReturn) }
  }

  @objc func reload(_ sender: Any?) {
    if web.url?.host == home.host { web.reload() } else { open() }
  }

  // MARK: menus (the Edit menu is what makes Cmd+V paste into the page)

  func menu() -> NSMenu {
    let bar = NSMenu()
    func add(_ title: String, _ items: [NSMenuItem]) {
      let top = NSMenuItem()
      let sub = NSMenu(title: title)
      items.forEach(sub.addItem)
      top.submenu = sub
      bar.addItem(top)
    }
    func item(_ title: String, _ action: Selector?, _ key: String, _ mods: NSEvent.ModifierFlags = .command) -> NSMenuItem {
      let i = NSMenuItem(title: title, action: action, keyEquivalent: key)
      i.keyEquivalentModifierMask = mods
      return i
    }
    add("Trials", [
      item("About Trials", #selector(NSApplication.orderFrontStandardAboutPanel(_:)), ""),
      .separator(),
      item("Hide Trials", #selector(NSApplication.hide(_:)), "h"),
      item("Hide Others", #selector(NSApplication.hideOtherApplications(_:)), "h", [.command, .option]),
      item("Show All", #selector(NSApplication.unhideAllApplications(_:)), ""),
      .separator(),
      item("Quit Trials", #selector(NSApplication.terminate(_:)), "q"),
    ])
    add("Edit", [
      item("Undo", Selector(("undo:")), "z"),
      item("Redo", Selector(("redo:")), "z", [.command, .shift]),
      .separator(),
      item("Cut", #selector(NSText.cut(_:)), "x"),
      item("Copy", #selector(NSText.copy(_:)), "c"),
      item("Paste", #selector(NSText.paste(_:)), "v"),
      item("Select All", #selector(NSText.selectAll(_:)), "a"),
    ])
    add("View", [
      item("Reload", #selector(reload(_:)), "r"),
      item("Enter Full Screen", #selector(NSWindow.toggleFullScreen(_:)), "f", [.command, .control]),
    ])
    add("Window", [
      item("Minimize", #selector(NSWindow.performMiniaturize(_:)), "m"),
      item("Zoom", #selector(NSWindow.performZoom(_:)), ""),
      item("Close", #selector(NSWindow.performClose(_:)), "w"),
    ])
    return bar
  }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
