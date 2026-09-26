import Foundation
import Combine
import UIKit

@MainActor
final class AuthViewModel: ObservableObject {
    @Published var currentUser: User?
    @Published var friends: [User] = []
    @Published var requests: [User] = []
    @Published var sent: [User] = []
    @Published var flames: [Flame] = []
    @Published var blocked: [User] = []
    @Published var unreadCount = 0
    @Published var nextCursor: String?
    @Published var inboxQuery = ""
    @Published var isBusy = false
    @Published var isRestoring = true
    @Published var isOffline = false
    @Published var status: String?
    @Published var error: String?
    @Published var recoveryCode: String?
    @Published var needsConsent = false
    let api = APIClient()
    private var refreshing = false
    private var inboxGeneration = 0
    private var inboxRequests = 0
    var isAuthenticated: Bool { currentUser != nil }

    func restore() async {
        defer { isRestoring = false }
        guard let token = api.token else { return }
        if let cached = OfflineStore.read(server: api.server, token: token) {
            currentUser = cached.user
            friends = cached.friends.friends; requests = cached.friends.requests; sent = cached.friends.sent
            flames = cached.inbox.flames; unreadCount = cached.inbox.unreadCount
            // Cursors are reloaded online; cached pages cannot be extended offline.
            isOffline = true
        }
        do {
            let user: User = try await api.request("/v1/me")
            guard api.token == token else { return }
            currentUser = user; isOffline = false
            needsConsent = user.consentVersion != PrivacyPolicy.version
        } catch {
            guard api.token == token else { return }
            handle(error, quietly: true)
        }
    }

    func authenticate(register: Bool, username: String, password: String, name: String, schoolId: String, birthDate: String) async {
        guard !isBusy else { return }
        isBusy = true; error = nil
        defer { isBusy = false }
        do {
            var body: [String: Any] = ["username": username, "password": password, "deviceName": UIDevice.current.model]
            if register {
                body.merge(["name": name, "schoolId": schoolId, "birthDate": birthDate,
                            "consent": true, "consentVersion": PrivacyPolicy.version]) { _, new in new }
            }
            let session: Session = try await api.request(register ? "/v1/register" : "/v1/login", method: "POST", body: body)
            try await install(session)
        } catch { handle(error) }
    }

    func replaceSession(path: String, body: [String: Any]) async -> Bool {
        guard !isBusy else { return false }
        isBusy = true; error = nil
        defer { isBusy = false }
        do {
            let session: Session = try await api.request(path, method: "POST", body: body)
            try await install(session)
            return true
        } catch { handle(error); return false }
    }

    private func install(_ session: Session) async throws {
        if let old = api.token { OfflineStore.clear(server: api.server, token: old) }
        api.token = session.token
        do { try SessionStore.write(session.token, server: api.server) }
        catch {
            let _: Acknowledgement? = try? await api.request("/v1/logout", method: "POST")
            api.token = nil; currentUser = nil
            friends = []; requests = []; sent = []; flames = []; blocked = []
            throw error
        }
        // Preserve the one-time code even if fetching the profile loses connectivity.
        recoveryCode = session.recoveryCode
        currentUser = try await api.request("/v1/me")
        needsConsent = currentUser?.consentVersion != PrivacyPolicy.version
        isOffline = false; status = nil
    }

    func refresh(preserveInbox: Bool = false) async {
        guard let token = api.token, !refreshing, !needsConsent else { return }
        refreshing = true
        defer { refreshing = false }
        do {
            let user: User = try await api.request("/v1/me")
            guard api.token == token else { return }
            currentUser = user; isOffline = false; status = nil
        } catch { if api.token == token { handle(error, quietly: true) }; return }
        // Apply each section independently so one failed request does not discard all data.
        do {
            let result: FriendsResult = try await api.request("/v1/friends")
            guard api.token == token else { return }
            friends = result.friends; requests = result.requests; sent = result.sent
        } catch { if api.token == token { handle(error, quietly: true) } }
        guard api.token == token else { return }
        await loadInbox(preserveLoaded: preserveInbox)
        guard api.token == token else { return }
        do {
            let result: PeopleResult = try await api.request("/v1/blocks")
            guard api.token == token else { return }
            blocked = result.people
        } catch { if api.token == token { handle(error, quietly: true) } }
        guard api.token == token else { return }
        let _: Acknowledgement? = try? await api.request("/v1/activity", method: "POST")
        saveCache()
    }

    func loadInbox(append: Bool = false, preserveLoaded: Bool = false) async {
        guard let token = api.token else { return }
        if preserveLoaded && inboxRequests > 0 { return }
        inboxRequests += 1
        defer { inboxRequests -= 1 }
        if append && nextCursor == nil { return }
        inboxGeneration += 1
        let generation = inboxGeneration
        var query = ["q": inboxQuery]
        if append { query["cursor"] = nextCursor }
        do {
            let result: InboxResult = try await api.request(APIClient.path("/v1/inbox", query: query))
            guard api.token == token, generation == inboxGeneration else { return }
            if preserveLoaded && flames.count > 50 {
                // Keep the user's position while browsing older pages. Pull-to-refresh reloads the list.
                unreadCount = result.unreadCount
                isOffline = false
                return
            }
            if append {
                let existing = Set(flames.map(\.id))
                flames += result.flames.filter { !existing.contains($0.id) }
            } else { flames = result.flames }
            unreadCount = result.unreadCount; nextCursor = result.nextCursor
            isOffline = false
            saveCache()
        } catch { if api.token == token, generation == inboxGeneration { handle(error, quietly: true) } }
    }

    private func saveCache() {
        guard let user = currentUser, let token = api.token, inboxQuery.isEmpty else { return }
        let snapshot = OfflineSnapshot(user: user, friends: FriendsResult(friends: friends, requests: requests, sent: sent),
            inbox: InboxResult(flames: Array(flames.prefix(50)), unreadCount: unreadCount, nextCursor: nil), savedAt: Date())
        do { try OfflineStore.save(snapshot, server: api.server, token: token) }
        catch { status = "Offline storage is unavailable. Your online data is unaffected." }
    }

    @discardableResult
    func perform(_ path: String, method: String = "POST", body: [String: Any] = [:]) async -> Bool {
        guard !isBusy else { return false }
        isBusy = true; error = nil
        defer { isBusy = false }
        do {
            let _: Acknowledgement = try await api.request(path, method: method, body: body)
            if path == "/v1/consent" { needsConsent = false }
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
        } catch {
            if !delete, error is URLError {
                do {
                    try clearSession()
                    self.error = "Signed out on this device. The server could not be reached to revoke the remote session. You can revoke it later from Active sessions."
                } catch { handle(error) }
            } else { handle(error) }
        }
    }

    func configureServer(_ address: String) async {
        do { try api.configure(address); await restore() }
        catch { handle(error) }
    }

    func handle(_ failure: Error, quietly: Bool = false) {
        if failure is CancellationError || (failure as? URLError)?.code == .cancelled { return }
        if let apiError = failure as? APIError {
            if apiError.status == 401, api.token != nil {
                do { try clearSession() } catch { self.error = error.localizedDescription; return }
            }
            if apiError.status == 428 { needsConsent = true; return }
        }
        if failure is URLError { isOffline = true }
        if quietly { status = failure.localizedDescription }
        else { error = failure.localizedDescription }
    }

    private func clearSession() throws {
        try SessionStore.write(nil, server: api.server)
        if let token = api.token { OfflineStore.clear(server: api.server, token: token) }
        api.token = nil; currentUser = nil
        friends = []; requests = []; sent = []; flames = []; blocked = []
        unreadCount = 0; nextCursor = nil; inboxQuery = ""
        needsConsent = false; recoveryCode = nil; isOffline = false; status = nil
        DailyReminder.disable()
    }
}
