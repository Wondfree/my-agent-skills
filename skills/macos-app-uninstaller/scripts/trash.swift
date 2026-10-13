import AppKit
import Foundation

// Called only after Python has checked the approved manifest and filesystem snapshots.
// The only mutation is FileManager.trashItem; never remove items permanently.
let arguments = Array(CommandLine.arguments.dropFirst())
guard arguments.count >= 2 else {
    fputs("Usage: swift trash.swift BUNDLE_ID PATH ...\n", stderr)
    exit(2)
}
let bundleID = arguments[0]
let paths = Array(arguments.dropFirst())
let fm = FileManager.default

guard NSRunningApplication.runningApplications(withBundleIdentifier: bundleID).isEmpty else {
    fputs("REFUSED: Target application is running; quit it and rescan.\n", stderr)
    exit(2)
}

for path in paths {
    do {
        let attributes = try fm.attributesOfItem(atPath: path)
        if (attributes[.type] as? FileAttributeType) == .typeSymbolicLink {
            fputs("REFUSED: Symbolic link encountered: \(path)\n", stderr)
            exit(2)
        }
    } catch {
        fputs("REFUSED: Preflight failed at \(path): \(error)\n", stderr)
        exit(2)
    }
}

var failures = 0
for path in paths {
    do {
        var resultingURL: NSURL?
        try fm.trashItem(at: URL(fileURLWithPath: path), resultingItemURL: &resultingURL)
        print("MOVED\t\(path)\t\(resultingURL?.path ?? "(destination unknown)")")
    } catch {
        failures += 1
        print("FAILED\t\(path)\t\(error)")
    }
}
print("RESULT\t\(paths.count - failures) moved, \(failures) failed")
exit(failures > 0 ? 3 : 0)
