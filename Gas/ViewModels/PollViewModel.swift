import Foundation
import Combine

@MainActor
final class PollViewModel: ObservableObject {
    @Published var polls: [Poll] = []
    @Published var currentIndex = 0
    @Published var answered = 0
    @Published var totalPolls = 12
    @Published var isLoading = false
    @Published var isSubmitting = false
    @Published var coinsEarned: Int?
    @Published var error: String?
    var currentPoll: Poll? { polls.indices.contains(currentIndex) ? polls[currentIndex] : nil }

    func load(_ auth: AuthViewModel) async {
        guard !isLoading, !isSubmitting else { return }
        let sessionToken = auth.api.token
        isLoading = true
        error = nil
        defer { isLoading = false }
        do {
            let response: PollsResult = try await auth.api.request("/v1/polls")
            guard auth.api.token == sessionToken else { return }
            polls = response.polls
            answered = response.answered
            totalPolls = response.total
            currentIndex = 0
        } catch {
            guard auth.api.token == sessionToken else { return }
            self.error = error.localizedDescription
            auth.handle(error)
        }
    }

    func submit(_ option: Poll.PollOption, auth: AuthViewModel) async {
        guard let poll = currentPoll, !isSubmitting else { return }
        let sessionToken = auth.api.token
        isSubmitting = true
        defer { isSubmitting = false }
        do {
            let result: VoteResult = try await auth.api.request("/v1/votes", method: "POST", body: ["pollId": poll.id, "selectedUserId": option.userId])
            guard auth.api.token == sessionToken else { return }
            polls.removeAll { $0.id == poll.id }
            if currentIndex >= polls.count { currentIndex = 0 }
            answered += 1
            coinsEarned = result.coinsEarned
            await auth.refresh()
        } catch {
            guard auth.api.token == sessionToken else { return }
            self.error = error.localizedDescription
            auth.handle(error)
            // Refresh before retrying: a lost response may still have committed the vote.
            isSubmitting = false
            await load(auth)
        }
    }

    func nextPoll() {
        guard !polls.isEmpty, !isSubmitting else { return }
        currentIndex = (currentIndex + 1) % polls.count
    }
    func shuffleOptions() {
        guard polls.indices.contains(currentIndex), !isSubmitting else { return }
        polls[currentIndex].options.shuffle()
    }
}
