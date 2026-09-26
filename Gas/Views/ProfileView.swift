import SwiftUI

struct ProfileView: View {
    @EnvironmentObject var auth: AuthViewModel
    @State private var reminder = DailyReminder.enabled
    @State private var updatingReminder = false
    var body: some View {
        NavigationView {
            List {
                if let user = auth.currentUser {
                    Section {
                        Label(user.name, systemImage: "person.crop.circle.fill").font(.title2.bold())
                        Text("@\(user.username)")
                        Text(user.school).foregroundColor(.secondary)
                        NavigationLink("Edit Profile") { EditProfileView() }
                    }
                    Section("Activity") {
                        Label("\(user.coins ?? 0) coins", systemImage: "star.circle.fill")
                        Text("Friends: \(auth.friends.count)")
                        NavigationLink("Coin History") { LedgerView() }
                    }
                    if user.hasRecoveryCode != true {
                        Text("Protect your account: create a recovery code in Password & Recovery.").foregroundColor(.orange)
                    }
                }
                Section("Account") {
                    NavigationLink("Password & Recovery") { PasswordView() }
                    NavigationLink("Active Sessions") { SessionsView() }
                    NavigationLink("My Reports") { ReportsView() }
                    NavigationLink("Export or Delete My Data") { AccountDataView() }
                }
                Section(footer: Text("A reminder at 8 PM in your device’s time zone. This is not a notification about incoming compliments.")) {
                    Toggle("Daily poll reminder", isOn: Binding(get: { reminder }, set: { value in
                        Task {
                            updatingReminder = true
                            defer { updatingReminder = false }
                            do {
                                if value { try await DailyReminder.enable() }
                                else { DailyReminder.disable() }
                                reminder = DailyReminder.enabled
                            } catch { auth.handle(error) }
                        }
                    })).disabled(updatingReminder)
                }
                Section {
                    NavigationLink("Privacy Information") { PrivacyView() }
                    Button("Log Out") { Task { await auth.signOut() } }.disabled(auth.isBusy)
                }
            }.navigationTitle("Profile").refreshable { await auth.refresh() }
        }.navigationViewStyle(.stack)
    }
}
