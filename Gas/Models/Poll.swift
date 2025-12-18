//
//  Poll.swift
//  Gas
//
//  Created by Gas Team
//

import Foundation

struct Poll: Identifiable, Codable {
    let id: String
    var question: String
    var emoji: String
    var options: [PollOption]
    var backgroundColor: String
    
    struct PollOption: Identifiable, Codable {
        let id: String
        var userId: String
        var userName: String
    }
}

struct PollResponse: Codable {
    let pollId: String
    let selectedUserId: String
    let responderId: String
    let timestamp: Date
}

struct Flame: Identifiable, Codable {
    let id: String
    var recipientId: String
    var senderId: String?
    var senderGender: User.Gender?
    var pollQuestion: String
    var timestamp: Date
    var isRead: Bool
}
