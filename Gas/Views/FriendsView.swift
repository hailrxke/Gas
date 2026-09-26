import SwiftUI

struct FriendsView: View {
    @EnvironmentObject var auth: AuthViewModel
    @State private var query = ""
    @State private var results: [User] = []
    @State private var searched = false
    @State private var searching = false

    var body: some View {
        NavigationView {
            List {
                Section(header: Text("Find friends at your school"), footer: Text("Search by name or username within your selected school.")) {
                    HStack {
                        TextField("Name or username", text: $query)
                            .textInputAutocapitalization(.never)
                            .disableAutocorrection(true)
                        Button("Search") { Task { await search() } }
                            .disabled(query.count < 2 || searching)
                    }
                    if searching { ProgressView() }
                    if searched && results.isEmpty { Text("No matching friends found.").foregroundColor(.secondary) }
                    ForEach(results) { person in
                        HStack {
                            personLabel(person)
                            Spacer()
                            if auth.friends.contains(where: { $0.id == person.id }) {
                                Text("Friends").foregroundColor(.secondary)
                            } else if auth.sent.contains(where: { $0.id == person.id }) {
                                Text("Request sent").foregroundColor(.secondary)
                            } else {
                                Button("Add") { connect(person) }.disabled(auth.isBusy)
                            }
                        }
                    }
                }
                Section { NavigationLink("Invitations") { InviteView() } }
                Section("Incoming requests") {
                    if auth.requests.isEmpty { Text("No incoming requests.").foregroundColor(.secondary) }
                    ForEach(auth.requests) { person in
                        VStack(alignment: .leading) {
                            personLabel(person)
                            HStack {
                                Button("Accept") { connect(person) }
                                Spacer()
                                Button("Decline", role: .destructive) { remove(person) }
                            }.buttonStyle(.borderless).disabled(auth.isBusy)
                        }
                    }
                }
                Section("Friends · \(auth.friends.count)") {
                    if auth.friends.isEmpty { Text("Connect with at least four accepted friends to unlock polls.").foregroundColor(.secondary) }
                    ForEach(auth.friends) { person in
                        personLabel(person)
                            .swipeActions {
                                Button("Remove", role: .destructive) { remove(person) }
                                Button("Block", role: .destructive) {
                                    Task { await auth.perform("/v1/blocks", body: ["userId": person.id]) }
                                }
                            }
                    }
                }
                Section("Sent requests") {
                    ForEach(auth.sent) { person in
                        HStack {
                            personLabel(person)
                            Spacer()
                            Button("Cancel") { remove(person) }.disabled(auth.isBusy)
                        }
                    }
                }
                Section("Blocked users") {
                    ForEach(auth.blocked) { person in
                        HStack {
                            personLabel(person)
                            Spacer()
                            Button("Unblock") {
                                Task { await auth.perform("/v1/blocks", method: "DELETE", body: ["userId": person.id]) }
                            }.disabled(auth.isBusy)
                        }
                    }
                }
            }
            .navigationTitle("Friends")
            .refreshable { await auth.refresh() }
            .task { await auth.refresh() }
            .onChange(of: query) { _ in results = []; searched = false }
        }.navigationViewStyle(.stack)
    }

    private func personLabel(_ person: User) -> some View {
        VStack(alignment: .leading) {
            Text(person.name).font(.headline)
            Text("@\(person.username)").font(.caption).foregroundColor(.secondary)
        }
    }
    private func connect(_ person: User) {
        Task { await auth.perform("/v1/friends", body: ["userId": person.id]) }
    }
    private func remove(_ person: User) {
        Task { await auth.perform("/v1/friends", method: "DELETE", body: ["userId": person.id]) }
    }
    private func search() async {
        searching = true
        searched = false
        let term = query.trimmingCharacters(in: .whitespacesAndNewlines)
        defer { searching = false }
        do {
            let response: PeopleResult = try await auth.api.request(APIClient.path("/v1/people", query: ["q": term]))
            guard query.trimmingCharacters(in: .whitespacesAndNewlines) == term else { return }
            results = response.people
            searched = true
        } catch { auth.handle(error) }
    }
}
