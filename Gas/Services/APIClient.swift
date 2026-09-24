import Foundation
import Security

struct APIError: LocalizedError {
    let status: Int
    let message: String
    var errorDescription: String? { message }
}

// Tokens never go into UserDefaults. A separate Keychain entry is used per server.
enum SessionStore {
    static func read(server: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "app.gas.korea.session",
            kSecAttrAccount as String: server,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func write(_ token: String?, server: String) throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "app.gas.korea.session",
            kSecAttrAccount as String: server
        ]
        if let token = token {
            let attributes: [String: Any] = [
                kSecValueData as String: Data(token.utf8),
                kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
            ]
            var status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
            if status == errSecItemNotFound {
                status = SecItemAdd(query.merging(attributes) { _, new in new } as CFDictionary, nil)
            }
            guard status == errSecSuccess else {
                throw APIError(status: 0, message: "Could not securely save your session. Please try again.")
            }
        } else {
            let status = SecItemDelete(query as CFDictionary)
            guard status == errSecSuccess || status == errSecItemNotFound else {
                throw APIError(status: 0, message: "Could not remove your saved session.")
            }
        }
    }
}

@MainActor
final class APIClient {
    nonisolated static var configuredServer: String {
        UserDefaults.standard.string(forKey: "gas.server") ?? "http://localhost:8080"
    }
    var server: String
    var token: String?

    init() {
        server = Self.configuredServer
        token = SessionStore.read(server: server)
    }

    func configure(_ address: String) throws {
        let cleaned = address.trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard let url = URL(string: cleaned), let host = url.host,
              url.user == nil, url.password == nil, url.query == nil, url.fragment == nil,
              url.path.isEmpty,
              url.scheme == "https" || (url.scheme == "http" && (host == "localhost" || host.hasSuffix(".local") || host == "127.0.0.1")) else {
            throw APIError(status: 0, message: "Enter an HTTPS address. For local testing, use http://localhost:8080 or a .local address.")
        }
        server = cleaned
        UserDefaults.standard.set(cleaned, forKey: "gas.server")
        token = SessionStore.read(server: cleaned)
    }

    func request<T: Decodable>(_ path: String, method: String = "GET", body: [String: Any]? = nil) async throws -> T {
        guard let url = URL(string: server + path) else {
            throw APIError(status: 0, message: "Please check the server address.")
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 20
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token = token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let body = body {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let response = response as? HTTPURLResponse else { throw URLError(.badServerResponse) }
        guard (200..<300).contains(response.statusCode) else {
            let error = try? JSONDecoder().decode(ErrorBody.self, from: data)
            throw APIError(status: response.statusCode, message: error?.error ?? "Could not connect to the server.")
        }
        return try JSONDecoder().decode(T.self, from: data)
    }

    private struct ErrorBody: Decodable { let error: String }
}
