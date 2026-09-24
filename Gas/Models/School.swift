import Foundation

// School names are self-reported in the MVP, not proof of enrollment.
struct School: Identifiable, Codable {
    let name: String
    var id: String { name }
}
