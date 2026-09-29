import Foundation

@main
struct ServerAddressChecks {
    static func main() throws {
        let commonAllowed = ["https://api.example.com", "http://localhost:8080", "http://127.0.0.1:8080", "http://archlinux.local:8080"]
        let privateAddresses = ["http://10.12.249.108:8080", "http://10.0.0.1", "http://172.16.0.1", "http://172.31.255.254", "http://192.168.1.2"]
        let rejected = ["http://example.com", "http://8.8.8.8", "http://172.15.0.1", "http://172.32.0.1", "http://192.169.1.1", "http://10.0.0.256", "http://10.1.2.3.evil.example", "http://10.1.2.3/health", "http://10.1.2.3/v1", "https://user:pass@example.com", "https://example.com?token=x", "https://example.com#fragment", "ftp://localhost", "https://example.com:99999"]
        for value in commonAllowed { _ = try ServerAddress.normalize(value) }
        let normalized = try ServerAddress.normalize("  http://localhost:8080/\n")
        precondition(normalized == "http://localhost:8080")
        #if DEBUG
        for value in privateAddresses { _ = try ServerAddress.normalize(value) }
        let invalid = rejected
        #else
        let invalid = rejected + privateAddresses
        #endif
        for value in invalid {
            do {
                _ = try ServerAddress.normalize(value)
                fatalError("Unexpectedly accepted: \(value)")
            } catch is ServerAddress.InvalidAddress { }
        }
        print("Server address policy checks passed")
    }
}
