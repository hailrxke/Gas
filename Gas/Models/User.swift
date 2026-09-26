import Foundation

struct User: Identifiable, Codable {
    let id: String
    let username: String
    let name: String
    let school: String
    let schoolId: String
    let age: Int?
    let birthDate: String?
    let coins: Int?
    let hasRecoveryCode: Bool?
    let consentVersion: String?
}
struct Session: Decodable { let token: String; let recoveryCode: String? }
struct RecoveryResult: Decodable { let recoveryCode: String }
struct Acknowledgement: Decodable { let ok: Bool }
struct PeopleResult: Decodable { let people: [User] }
struct FriendsResult: Codable {
    let friends: [User]
    let requests: [User]
    let sent: [User]
}
struct DeviceSession: Identifiable, Decodable {
    let id: String
    let device: String
    let created: Double
    let expires: Double
    let current: Bool
}
struct SessionsResult: Decodable { let sessions: [DeviceSession] }
struct CoinEntry: Identifiable, Decodable {
    let id: String
    let amount: Int
    let reason: String
    let timestamp: String
}
struct LedgerResult: Decodable { let entries: [CoinEntry] }
struct Report: Identifiable, Decodable {
    let id: String
    let reason: String
    let timestamp: String
    let status: String
    let resolution: String
}
struct ReportsResult: Decodable { let reports: [Report] }
struct Invitation: Decodable { let code: String; let expires: Double }
