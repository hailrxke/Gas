import SwiftUI
import UIKit

struct RecoveryCodeView: View {
    @Environment(\.dismiss) private var dismiss
    let code: String
    @State private var saved = false
    var body: some View {
        NavigationView {
            Form {
                Text("Save this recovery code in a safe place. It lets you reset your password. Anyone with your username and this code can take over your account.")
                Text(code).font(.system(.body, design: .monospaced)).textSelection(.enabled)
                Text("This code replaces any previous code. We cannot show it again after you close this screen.")
                Button("Copy code") {
                    UIPasteboard.general.setItems([[UIPasteboard.typeAutomatic: code]], options: [.localOnly: true, .expirationDate: Date().addingTimeInterval(120)])
                }
                Toggle("I saved my recovery code", isOn: $saved)
                Button("Done") { dismiss() }.disabled(!saved)
            }.navigationTitle("Recovery Code")
        }.interactiveDismissDisabled()
    }
}

struct RecoverAccountView: View {
    @EnvironmentObject var auth: AuthViewModel
    @State private var username = ""
    @State private var code = ""
    @State private var password = ""
    @State private var confirmation = ""
    var body: some View {
        Form {
            Text("Enter the recovery code you saved when you created your account or changed your password. Recovery signs out every other device and gives you a new code.")
            TextField("Username", text: $username).textInputAutocapitalization(.never).disableAutocorrection(true)
            TextField("Recovery code", text: $code).textInputAutocapitalization(.characters).disableAutocorrection(true)
            SecureField("New password", text: $password).textContentType(.newPassword)
            SecureField("Confirm password", text: $confirmation).textContentType(.newPassword)
            Button("Reset Password") {
                Task {
                    if await auth.replaceSession(path: "/v1/recover", body: ["username": username, "recoveryCode": code, "newPassword": password]) {
                        code = ""; password = ""; confirmation = ""
                    }
                }
            }.disabled(auth.isBusy || username.count < 3 || code.count < 32 || password.count < 10 || password.count > 128 || password != confirmation)
            Text("Without your password or saved recovery code, automatic recovery is unavailable.").font(.footnote)
        }.navigationTitle("Recover Account")
    }
}

struct EditProfileView: View {
    @EnvironmentObject var auth: AuthViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var username = ""
    @State private var school: School?
    @State private var password = ""
    @State private var confirmChange = false
    private var changingSchool: Bool { school != nil && school?.id != auth.currentUser?.schoolId }
    var body: some View {
        Form {
            TextField("Name or nickname", text: $name)
            TextField("Username", text: $username).textInputAutocapitalization(.never).disableAutocorrection(true)
            NavigationLink(school?.displayName ?? auth.currentUser?.school ?? "Choose School") { SchoolPickerView(selection: $school) }
            if changingSchool {
                Text("Changing schools removes all friendships, pending requests and your invitation code. Your vote history and points remain.")
                SecureField("Current password", text: $password).textContentType(.password)
            }
            Button("Save Changes") {
                if changingSchool { confirmChange = true }
                else { Task { await save() } }
            }.disabled(auth.isBusy || name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || name.count > 40 || username.count < 3 || (changingSchool && password.count < 10))
        }
        .navigationTitle("Edit Profile")
        .onAppear { name = auth.currentUser?.name ?? ""; username = auth.currentUser?.username ?? "" }
        .confirmationDialog("Change schools and remove your friendships?", isPresented: $confirmChange, titleVisibility: .visible) {
            Button("Change School", role: .destructive) { Task { await save() } }
        }
    }
    private func save() async {
        if await auth.perform("/v1/me", method: "PATCH", body: ["name": name, "username": username,
            "schoolId": school?.id ?? auth.currentUser?.schoolId ?? "", "confirmSchoolChange": changingSchool, "password": password]) {
            password = ""; dismiss()
        }
    }
}

struct PasswordView: View {
    @EnvironmentObject var auth: AuthViewModel
    @State private var current = ""
    @State private var password = ""
    @State private var confirmation = ""
    @State private var message: String?
    var body: some View {
        Form {
            SecureField("Current password", text: $current).textContentType(.password)
            Section("Change password") {
                SecureField("New password", text: $password).textContentType(.newPassword)
                SecureField("Confirm password", text: $confirmation).textContentType(.newPassword)
                Text("Changing your password signs out all other sessions and replaces your recovery code.")
                Button("Change Password") {
                    Task {
                        if await auth.replaceSession(path: "/v1/password", body: ["password": current, "newPassword": password]) {
                            current = ""; password = ""; confirmation = ""; message = "Password changed. Other sessions were signed out."
                        }
                    }
                }.disabled(auth.isBusy || current.count < 10 || password.count < 10 || password.count > 128 || password != confirmation)
            }
            Section("Recovery code") {
                Text("If you lost your saved recovery code, create a replacement using your current password. The previous code stops working immediately.")
                Button("Replace Recovery Code") {
                    Task {
                        guard !auth.isBusy else { return }
                        auth.isBusy = true
                        defer { auth.isBusy = false }
                        do {
                            let result: RecoveryResult = try await auth.api.request("/v1/recovery-code", method: "POST", body: ["password": current])
                            auth.recoveryCode = result.recoveryCode; current = ""
                        } catch { auth.handle(error) }
                    }
                }.disabled(auth.isBusy || current.count < 10)
            }
            if let message = message { Text(message).foregroundColor(.secondary) }
        }.navigationTitle("Password & Recovery")
    }
}

struct SessionsView: View {
    @EnvironmentObject var auth: AuthViewModel
    @State private var sessions: [DeviceSession] = []
    @State private var loading = false
    var body: some View {
        List {
            if loading { ProgressView() }
            ForEach(sessions) { session in
                VStack(alignment: .leading, spacing: 6) {
                    Text(session.device + (session.current ? " · This session" : "")).font(.headline)
                    if session.created > 0 {
                        Text("Signed in: \(Date(timeIntervalSince1970: session.created).formatted(date: .abbreviated, time: .shortened))").font(.caption)
                    } else { Text("Sign-in date unavailable").font(.caption) }
                    Text("Expires: \(Date(timeIntervalSince1970: session.expires).formatted(date: .abbreviated, time: .omitted))").font(.caption)
                    if !session.current {
                        Button("Sign Out Session", role: .destructive) {
                            Task { if await auth.perform("/v1/sessions", method: "DELETE", body: ["id": session.id]) { await load() } }
                        }.disabled(auth.isBusy)
                    }
                }
            }
            Button("Sign Out All Other Sessions", role: .destructive) {
                Task { if await auth.perform("/v1/sessions", method: "DELETE", body: ["allOthers": true]) { await load() } }
            }.disabled(auth.isBusy || sessions.filter { !$0.current }.isEmpty)
        }.navigationTitle("Active Sessions").task { await load() }.refreshable { await load() }
    }
    private func load() async {
        loading = true; defer { loading = false }
        do { let result: SessionsResult = try await auth.api.request("/v1/sessions"); sessions = result.sessions }
        catch { auth.handle(error) }
    }
}

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]
    func makeUIViewController(context: Context) -> UIActivityViewController { UIActivityViewController(activityItems: items, applicationActivities: nil) }
    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}

struct AccountDataView: View {
    @EnvironmentObject var auth: AuthViewModel
    @State private var password = ""
    @State private var confirmingDelete = false
    @State private var exporting = false
    @State private var file: URL?
    @State private var sharing = false
    var body: some View {
        Form {
            SecureField("Current password", text: $password).textContentType(.password)
            Section("Export") {
                Text("Download your profile, friendships, votes, coin history and reports as JSON. Anonymous sender identities are never included. Keep the exported file private.")
                Button(exporting ? "Preparing…" : "Export My Data") { Task { await export() } }
                    .disabled(auth.isBusy || exporting || password.count < 10)
            }
            Section("Delete account") {
                Text("This permanently removes your profile, sessions, friendships and coin balance. Compliments already delivered remain anonymous, with your account link removed. This cannot be undone.")
                Button("Delete Account", role: .destructive) { confirmingDelete = true }
                    .disabled(auth.isBusy || exporting || password.count < 10)
            }
        }.navigationTitle("Your Data")
        .confirmationDialog("Permanently delete your account?", isPresented: $confirmingDelete, titleVisibility: .visible) {
            Button("Delete Permanently", role: .destructive) { Task { await auth.signOut(delete: true, password: password); password = "" } }
        }
        .sheet(isPresented: $sharing, onDismiss: cleanup) { if let file = file { ShareSheet(items: [file]) } }
        .onDisappear { if !sharing { cleanup() } }
    }
    private func cleanup() { if let file = file { try? FileManager.default.removeItem(at: file) }; file = nil }
    private func export() async {
        exporting = true; defer { exporting = false }
        do {
            let data = try await auth.api.requestData("/v1/export", method: "POST", body: ["password": password])
            cleanup()
            let url = FileManager.default.temporaryDirectory.appendingPathComponent("gas-export-\(UUID().uuidString).json")
            try data.write(to: url, options: [.atomic, .completeFileProtection])
            file = url; password = ""; sharing = true
        } catch { auth.handle(error) }
    }
}

struct LedgerView: View {
    @EnvironmentObject var auth: AuthViewModel
    @State private var entries: [CoinEntry] = []
    var body: some View {
        List {
            Text("Latest 100 entries. Export your data for the full history. Coins have no cash value.").font(.footnote)
            ForEach(entries) { entry in
                VStack(alignment: .leading) {
                    Text("\(entry.amount > 0 ? "+" : "")\(entry.amount) · \(entry.reason)")
                    Text(entry.timestamp).font(.caption).foregroundColor(.secondary)
                }
            }
        }.navigationTitle("Coin History").task { await load() }.refreshable { await load() }
    }
    private func load() async {
        do { let result: LedgerResult = try await auth.api.request("/v1/ledger"); entries = result.entries }
        catch { auth.handle(error) }
    }
}

struct ReportsView: View {
    @EnvironmentObject var auth: AuthViewModel
    @State private var reports: [Report] = []
    @State private var unblocking: Report?
    @State private var resetBlocks = false
    var body: some View {
        List {
            Text("Latest 100 reports. Older reports may be removed by the retention policy. You can reset all anonymous sender blocks even after a report expires.").font(.footnote)
            Button("Reset All Anonymous Sender Blocks", role: .destructive) { resetBlocks = true }
                .disabled(auth.isBusy)
            if reports.isEmpty { Text("No reports yet.") }
            ForEach(reports) { report in
                VStack(alignment: .leading, spacing: 8) {
                    Text(report.reason).font(.headline)
                    Text(report.status.replacingOccurrences(of: "_", with: " ").capitalized).foregroundColor(.secondary)
                    if !report.resolution.isEmpty { Text(report.resolution) }
                    Button("Undo Sender Block") { unblocking = report }.disabled(auth.isBusy)
                }
            }
        }.navigationTitle("My Reports").task { await load() }.refreshable { await load() }
        .confirmationDialog("Allow compliments from all anonymously blocked senders again?", isPresented: $resetBlocks, titleVisibility: .visible) {
            Button("Reset Blocks", role: .destructive) { Task { await auth.perform("/v1/blocks/anonymous", method: "DELETE") } }
        }
        .confirmationDialog("Allow this sender’s compliments to appear again? Their identity stays hidden.", isPresented: Binding(get: { unblocking != nil }, set: { if !$0 { unblocking = nil } }), titleVisibility: .visible) {
            if let report = unblocking {
                Button("Unblock Sender") { Task { await auth.perform("/v1/reports/unblock", body: ["id": report.id]); unblocking = nil } }
            }
        }
    }
    private func load() async {
        do { let result: ReportsResult = try await auth.api.request("/v1/reports"); reports = result.reports }
        catch { auth.handle(error) }
    }
}
