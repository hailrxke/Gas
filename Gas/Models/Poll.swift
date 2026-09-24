import Foundation

struct Poll: Identifiable, Codable {
    let id: String
    let question: String
    let emoji: String
    var options: [PollOption]
    let backgroundColor: String

    struct PollOption: Identifiable, Codable {
        let id: String
        let userId: String
        let userName: String
    }
}

struct PollsResult: Decodable {
    let polls: [Poll]
    let answered: Int
    let total: Int
}
struct VoteResult: Decodable { let coinsEarned: Int }
struct InboxResult: Decodable { let flames: [Flame] }
struct Flame: Identifiable, Codable {
    let id: String
    let pollQuestion: String
    let day: String
    let isRead: Bool
}
