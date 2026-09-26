import Foundation
import CryptoKit

struct OfflineSnapshot: Codable {
    let user: User
    let friends: FriendsResult
    let inbox: InboxResult
    let savedAt: Date
}

// iOS file protection, excluded from backups, keyed by server AND session.
// No tokens, passwords or recovery codes are written to this file.
enum OfflineStore {
    private static func location(server: String, token: String) throws -> URL {
        let root = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
        var directory = root.appendingPathComponent("Offline", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        try directory.setResourceValues(values)
        let hash = SHA256.hash(data: Data((server + "\n" + token).utf8)).map { String(format: "%02x", $0) }.joined()
        return directory.appendingPathComponent(hash + ".json")
    }
    static func read(server: String, token: String) -> OfflineSnapshot? {
        guard let url = try? location(server: server, token: token),
              let data = try? Data(contentsOf: url),
              let snapshot = try? JSONDecoder().decode(OfflineSnapshot.self, from: data) else { return nil }
        guard Date().timeIntervalSince(snapshot.savedAt) < 7 * 86400 else {
            try? FileManager.default.removeItem(at: url)
            return nil
        }
        return snapshot
    }
    static func save(_ snapshot: OfflineSnapshot, server: String, token: String) throws {
        try JSONEncoder().encode(snapshot).write(to: location(server: server, token: token), options: [.atomic, .completeFileProtection])
    }
    static func clear(server: String, token: String) {
        if let url = try? location(server: server, token: token) { try? FileManager.default.removeItem(at: url) }
    }
}
