import SwiftUI
import WidgetKit

/// Watches the usage cache directory and refreshes the widget when it changes.
///
/// The menu bar app rewrites usage.json about once a minute, but nothing ever
/// told WidgetKit. A widget's own timeline policy is only a request, and the
/// system throttles it hard - gaps of five hours were observed - so the widget
/// sat there showing numbers that were hours out of date.
///
/// The directory is watched rather than the file: usage.json is replaced
/// atomically (write to a temp file, then rename), which invalidates any
/// descriptor opened on the file itself after the very first write.
final class UsageCacheWatcher {
    private var source: DispatchSourceFileSystemObject?
    private var descriptor: CInt = -1
    private var pending: DispatchWorkItem?

    init(directory: URL) {
        descriptor = open(directory.path, O_EVTONLY)
        guard descriptor >= 0 else { return }
        let source = DispatchSource.makeFileSystemObjectSource(
            fileDescriptor: descriptor,
            eventMask: [.write, .delete, .rename, .attrib],
            queue: .main
        )
        source.setEventHandler { [weak self] in self?.scheduleReload() }
        source.setCancelHandler { [weak self] in
            guard let self, self.descriptor >= 0 else { return }
            close(self.descriptor)
            self.descriptor = -1
        }
        source.resume()
        self.source = source
    }

    deinit {
        source?.cancel()
    }

    /// A single atomic replace emits several events; coalesce them so the
    /// widget is asked to reload once per write.
    private func scheduleReload() {
        pending?.cancel()
        let work = DispatchWorkItem { WidgetCenter.shared.reloadAllTimelines() }
        pending = work
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5, execute: work)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var watcher: UsageCacheWatcher?
    private var safetyTimer: Timer?

    /// Resolved via POSIX: inside the sandbox, NSHomeDirectory() returns the
    /// app's container rather than the real home directory.
    static var cacheDirectory: URL {
        let home = getpwuid(getuid())
            .flatMap { String(cString: $0.pointee.pw_dir) } ?? NSHomeDirectory()
        return URL(fileURLWithPath: home)
            .appendingPathComponent("Library/Application Support/AIQuotaBar")
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        watcher = UsageCacheWatcher(directory: Self.cacheDirectory)
        WidgetCenter.shared.reloadAllTimelines()

        // Backstop, in case a filesystem event is ever missed.
        safetyTimer = Timer.scheduledTimer(withTimeInterval: 600, repeats: true) { _ in
            WidgetCenter.shared.reloadAllTimelines()
        }
    }

    /// This is a background helper for the widget; closing the window must not
    /// stop it watching.
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }
}

@main
struct AIQuotaBarHostApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            ContentView()
                .onAppear { WidgetCenter.shared.reloadAllTimelines() }
        }
        .defaultSize(width: 400, height: 300)
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { WidgetCenter.shared.reloadAllTimelines() }
        }
    }
}
