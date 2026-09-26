import Foundation
import Combine

@MainActor
final class PollViewModel: ObservableObject {
    @Published var polls: [Poll] = []
    @Published var answered = 0
    @Published var totalPolls = 12
    @Published var skipped = 0
    @Published var minimumFriends = 4
    @Published var friendCount = 0
    @Published var isLoading = false
    @Published var isSubmitting = false
    @Published var coinsEarned: Int?
    @Published var error: String?
    private var day = ""
    var currentPoll: Poll? { polls.first }

    func load(_ auth: AuthViewModel) async {
        guard !isLoading, !isSubmitting else { return }
        let token = auth.api.token
        isLoading = true
        defer { isLoading = false }
        do {
            let response: PollsResult = try await auth.api.request("/v1/polls")
            guard auth.api.token == token else { return }
            polls = response.polls; answered = response.answered; totalPolls = response.total
            day = response.day; skipped = response.skipped
            minimumFriends = response.minimumFriends; friendCount = response.friendCount
        } catch {
            guard auth.api.token == token else { return }
            self.error = error.localizedDescription
            auth.handle(error, quietly: true)
        }
    }

    func submit(_ option: Poll.PollOption, auth: AuthViewModel) async {
        guard let poll = currentPoll, !isSubmitting else { return }
        let token = auth.api.token
        isSubmitting = true; error = nil
        do {
            let result: VoteResult = try await auth.api.request("/v1/votes", method: "POST", body: ["pollId": poll.id, "selectedUserId": option.userId, "day": day])
            guard auth.api.token == token else { isSubmitting = false; return }
            coinsEarned = result.coinsEarned
            await auth.refresh()
        } catch {
            if auth.api.token == token { self.error = error.localizedDescription; auth.handle(error, quietly: true) }
        }
        isSubmitting = false
        // A lost response may still have committed the vote. Always reload before retrying.
        if auth.api.token == token { await load(auth) }
    }

    func change(_ action: String, auth: AuthViewModel) async {
        guard !isSubmitting, !isLoading else { return }
        let token = auth.api.token
        isSubmitting = true; error = nil
        do {
            var body: [String: Any] = ["day": day]
            if let poll = currentPoll { body["pollId"] = poll.id }
            let _: Acknowledgement = try await auth.api.request("/v1/polls/" + action, method: "POST", body: body)
        } catch {
            if auth.api.token == token { self.error = error.localizedDescription; auth.handle(error, quietly: true) }
        }
        isSubmitting = false
        if auth.api.token == token { await load(auth) }
    }
}
