import SwiftUI

struct ProfileView: View {
    @EnvironmentObject var auth: AuthViewModel
    @State private var deleting = false
    @State private var confirmingDelete = false
    @State private var password = ""

    var body: some View {
        NavigationView {
            List {
                if let user = auth.currentUser {
                    Section {
                        Label(user.name, systemImage: "person.crop.circle.fill").font(.title2.bold())
                        Text("@\(user.username)")
                        Text(user.school).foregroundColor(.secondary)
                    }
                    Section("Activity") {
                        Label("\(user.coins ?? 0) coins", systemImage: "star.circle.fill")
                        Text("Friends: \(auth.friends.count)")
                        Text("Coins are participation points and have no cash value.").font(.footnote).foregroundColor(.secondary)
                    }
                }
                Section {
                    NavigationLink("Privacy information") { PrivacyView() }
                    Button("Log Out") { Task { await auth.signOut() } }.disabled(auth.isBusy)
                    Button("Delete Account", role: .destructive) { deleting = true }.disabled(auth.isBusy)
                }
            }
            .navigationTitle("Profile")
            .refreshable { await auth.refresh() }
            .sheet(isPresented: $deleting) {
                NavigationView {
                    Form {
                        if let error = auth.error { Text(error).foregroundColor(.red) }
                        Text("This deletes your account, friendships, and related voting records. This action cannot be undone.")
                        SecureField("Current password", text: $password).textContentType(.password)
                        Button("Continue", role: .destructive) { confirmingDelete = true }
                            .disabled(password.count < 10 || auth.isBusy)
                    }
                    .navigationTitle("Delete Account")
                    .toolbar { Button("Cancel") { deleting = false; password = "" } }
                    .confirmationDialog("Permanently delete your account?", isPresented: $confirmingDelete, titleVisibility: .visible) {
                        Button("Delete Permanently", role: .destructive) {
                            Task { await auth.signOut(delete: true, password: password); password = "" }
                        }
                    }
                }
            }
        }.navigationViewStyle(.stack)
    }
}
