import SwiftUI

struct InviteView: View {
    @EnvironmentObject var auth: AuthViewModel
    @State private var invitation: Invitation?
    @State private var code = ""
    @State private var busy = false
    @State private var sharing = false
    @State private var message: String?
    var body: some View {
        Form {
            Section("Invite a schoolmate") {
                Text("Share a code with someone at your school. You will still need to accept their friend request. Codes expire after seven days; creating a new one replaces the old one.")
                Button("Create New Invitation") {
                    Task {
                        busy = true; defer { busy = false }
                        do { invitation = try await auth.api.request("/v1/invites", method: "POST") }
                        catch { auth.handle(error) }
                    }
                }.disabled(busy)
                if let invitation = invitation {
                    Text(invitation.code).font(.system(.body, design: .monospaced)).textSelection(.enabled)
                    Text("Expires: \(Date(timeIntervalSince1970: invitation.expires).formatted(date: .abbreviated, time: .shortened))").font(.caption)
                    Button("Share Invitation") { sharing = true }
                }
            }
            Section("Have an invitation?") {
                TextField("Invitation code", text: $code).textInputAutocapitalization(.never).disableAutocorrection(true)
                Button("Send Friend Request") {
                    Task {
                        if await auth.perform("/v1/invites/accept", body: ["code": code.trimmingCharacters(in: .whitespacesAndNewlines)]) {
                            code = ""; message = "Request sent. Check Friends for the connection status."
                        }
                    }
                }.disabled(auth.isBusy || code.isEmpty)
                if let message = message { Text(message) }
            }
        }.navigationTitle("Invitations")
        .sheet(isPresented: $sharing) {
            if let invitation = invitation {
                ShareSheet(items: ["Join me on GAS! In Friends → Invitations, enter: \(invitation.code)\nChoose my school and use the same server: \(auth.api.server)"])
            }
        }
    }
}
