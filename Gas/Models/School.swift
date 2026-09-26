import Foundation

// Catalog membership is not proof of enrollment.
struct School: Identifiable, Codable, Equatable {
    let id: String
    let name: String
    let englishName: String
    let region: String
    let address: String
    let kind: String
    var displayName: String { englishName.isEmpty ? name : englishName }
}
struct SchoolsResult: Decodable { let schools: [School] }
enum PrivacyPolicy { static let version = "2026-09-27" }
