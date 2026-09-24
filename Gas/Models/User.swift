import Foundation

struct User: Identifiable, Codable {
    let id: String
    let username: String
    let name: String
    let school: String
    let age: Int?
    let coins: Int?
}

struct Session: Decodable { let token: String }
struct Acknowledgement: Decodable { let ok: Bool }
struct PeopleResult: Decodable { let people: [User] }
struct FriendsResult: Decodable {
    let friends: [User]
    let requests: [User]
    let sent: [User]
}
