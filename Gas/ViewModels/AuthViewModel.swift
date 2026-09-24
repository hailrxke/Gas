import Foundation
import Combine

@MainActor
final class AuthViewModel: ObservableObject {
    @Published var currentUser: User?
    @Published var friends: [User] = []
    @Published var requests: [User] = []
    @Published var sent: [User] = []
    @Published var flames: [Flame] = []
    @Published var blocked: [User] = []
    @Published var isBusy = false
    @Published var isRestoring = true
    @Published var error: String?
    let api = APIClient()
    private var refreshGeneration = 0
    var isAuthenticated: Bool { currentUser != nil }

    func restore() async {
        defer { isRestoring = false }
        guard let sessionToken = api.token else { return }
        do {
            let user: User = try await api.request("/v1/me")
            guard api.token == sessionToken else { return }
            currentUser = user
        } catch {
            guard api.token == sessionToken else { return }
            handle(error)
        }
    }

    func authenticate(register: Bool, username: String, password: String, name: String, school: String, age: Int) async {
        guard !isBusy else { return }
        isBusy = true
        error = nil
        defer { isBusy = false }
        do {
            var body: [String: Any] = ["username": username, "password": password]
            if register { body.merge(["name": name, "school": school, "age": age]) { _, new in new } }
            let session: Session = try await api.request(register ? "/v1/register" : "/v1/login", method: "POST", body: body)
            api.token = session.token
            do {
                try SessionStore.write(session.token, server: api.server)
            } catch {
                let _: Acknowledgement? = try? await api.request("/v1/logout", method: "POST")
                api.token = nil
                throw error
            }
            currentUser = try await api.request("/v1/me")
        } catch { handle(error) }
    }

    func refresh() async {
        guard let sessionToken = api.token else { return }
        refreshGeneration += 1
        let generation = refreshGeneration
        do {
            let user: User = try await api.request("/v1/me")
            let connections: FriendsResult = try await api.request("/v1/friends")
            let inbox: InboxResult = try await api.request("/v1/inbox")
            let blocks: PeopleResult = try await api.request("/v1/blocks")
            guard api.token == sessionToken, generation == refreshGeneration else { return }
            currentUser = user
            friends = connections.friends
            requests = connections.requests
            sent = connections.sent
            flames = inbox.flames
            blocked = blocks.people
        } catch {
            guard api.token == sessionToken, generation == refreshGeneration else { return }
            handle(error)
        }
    }

    @discardableResult
    func perform(_ path: String, method: String = "POST", body: [String: Any] = [:]) async -> Bool {
        guard !isBusy else { return false }
        isBusy = true
        error = nil
        defer { isBusy = false }
        do {
            let _: Acknowledgement = try await api.request(path, method: method, body: body)
            await refresh()
            return true
        } catch { handle(error); return false }
    }

    func signOut(delete: Bool = false, password: String = "") async {
        guard !isBusy else { return }
        isBusy = true
        defer { isBusy = false }
        do {
            let _: Acknowledgement = try await api.request(delete ? "/v1/me" : "/v1/logout", method: delete ? "DELETE" : "POST", body: delete ? ["password": password] : [:])
            try clearSession()
        } catch { handle(error) }
    }

    func configureServer(_ address: String) async {
        do {
            try api.configure(address)
            await restore()
        } catch { handle(error) }
    }

    func handle(_ failure: Error) {
        if let apiError = failure as? APIError, apiError.status == 401 {
            do { try clearSession() } catch { self.error = error.localizedDescription; return }
        }
        error = failure.localizedDescription
    }

    private func clearSession() throws {
        try SessionStore.write(nil, server: api.server)
        api.token = nil
        currentUser = nil
        friends = []; requests = []; sent = []; flames = []; blocked = []
    }
}
