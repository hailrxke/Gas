//
//  PollViewModel.swift
//  Gas
//
//  Created by Gas Team
//

import Foundation
import Combine

class PollViewModel: ObservableObject {
    @Published var currentPoll: Poll?
    @Published var currentIndex = 0
    @Published var coinsEarned = 18
    
    var totalPolls = 12
    private var polls: [Poll] = []
    
    func loadPolls() {
        // Mock data - in production, fetch from backend
        polls = [
            Poll(
                id: "1",
                question: "Best person to go camping with",
                emoji: "⛺️",
                options: [
                    Poll.PollOption(id: "1", userId: "u1", userName: "Elena"),
                    Poll.PollOption(id: "2", userId: "u2", userName: "Peggie"),
                    Poll.PollOption(id: "3", userId: "u3", userName: "Quy"),
                    Poll.PollOption(id: "4", userId: "u4", userName: "Angie")
                ],
                backgroundColor: "brown"
            ),
            Poll(
                id: "2",
                question: "Smiling 24/7",
                emoji: "😊",
                options: [
                    Poll.PollOption(id: "1", userId: "u5", userName: "Gary"),
                    Poll.PollOption(id: "2", userId: "u6", userName: "Taufik"),
                    Poll.PollOption(id: "3", userId: "u7", userName: "Runina"),
                    Poll.PollOption(id: "4", userId: "u8", userName: "Quy")
                ],
                backgroundColor: "blue"
            )
        ]
        currentPoll = polls.first
    }
    
    func submitResponse(selectedUserId: String) {
        // In production, send to backend
        print("User selected: \(selectedUserId)")
        coinsEarned = Int.random(in: 15...25)
    }
    
    func nextPoll() {
        currentIndex += 1
        if currentIndex < polls.count {
            currentPoll = polls[currentIndex]
        } else {
            currentIndex = 0
            currentPoll = polls.first
        }
    }
    
    func shuffleOptions() {
        guard var poll = currentPoll else { return }
        poll.options.shuffle()
        currentPoll = poll
    }
    
    func skipPoll() {
        nextPoll()
    }
}
