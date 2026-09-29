import Foundation

/// One policy for both newly entered and previously saved server addresses.
enum ServerAddress {
    #if DEBUG
    static let guidance = "Enter an HTTPS address, or a local HTTP address such as http://10.12.249.108:8080 for testing. Do not include /health or /v1."
    #else
    static let guidance = "Enter an HTTPS address. For local testing, use http://localhost:8080 or a .local address. Do not include /health or /v1."
    #endif

    struct InvalidAddress: LocalizedError {
        var errorDescription: String? { ServerAddress.guidance }
    }

    static func normalize(_ address: String) throws -> String {
        let cleaned = address.trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard let url = URL(string: cleaned), let host = url.host, !host.isEmpty,
              url.user == nil, url.password == nil, url.query == nil, url.fragment == nil,
              url.path.isEmpty, url.port == nil || (1...65535).contains(url.port!),
              url.scheme?.lowercased() == "https" ||
                (url.scheme?.lowercased() == "http" && allowsLocalHTTP(host)) else {
            throw InvalidAddress()
        }
        return cleaned
    }

    private static func allowsLocalHTTP(_ host: String) -> Bool {
        let host = host.lowercased()
        if host == "localhost" || host == "127.0.0.1" || host.hasSuffix(".local") { return true }
        #if DEBUG
        // Only canonical RFC 1918 IPv4 addresses; public HTTP remains disallowed.
        let parts = host.split(separator: ".", omittingEmptySubsequences: false)
        let octets = parts.compactMap { Int($0) }
        guard parts.count == 4, octets.count == 4,
              zip(parts, octets).allSatisfy({ part, value in
                  (0...255).contains(value) && String(value) == String(part)
              }) else { return false }
        return octets[0] == 10 ||
            (octets[0] == 172 && (16...31).contains(octets[1])) ||
            (octets[0] == 192 && octets[1] == 168)
        #else
        return false
        #endif
    }
}
