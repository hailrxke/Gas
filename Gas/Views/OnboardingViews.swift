import SwiftUI

struct PrivacyView: View {
    var body: some View {
        List {
            Section("Information we store") {
                Text("We store your username, name or nickname, date of birth, school selection, friendships, votes, coin history, sessions, consent and reports. Passwords, session tokens and recovery codes are stored on the server as verification hashes.")
                Text("Your birthday is private. School and age are self-reported; we do not verify your identity or enrollment. Do not impersonate others.")
            }
            Section("Who can see your information?") {
                Text("Students who select the same school can search for your name or username. Both people must accept a friendship before voting about each other.")
                Text("Polls require at least four accepted friends. Recipients see the question and day, without the sender’s identity. This reduces clues but cannot prevent guessing. The service operator can access voting records to operate the service and investigate reports.")
            }
            Section("Your controls") {
                Text("You can edit your profile, change your password, manage active sessions, export your data or delete your account in Profile. Keep your recovery code safe. Without your password or recovery code, automatic account recovery is unavailable.")
                Text("You can remove friends and block people. Report & Block hides that sender’s compliments without displaying their identity. My reports lets you see the operator’s response and undo that block. Removing a friendship may itself give someone a clue about who sent a compliment.")
            }
            Section("Storage and retention") {
                Text("Deleting your account removes your profile, credentials, friendships and personal coin ledger. Delivered compliments remain anonymous: your account link is removed from those records. Records with no remaining participants are deleted.")
                Text("The server includes a maintenance command to remove voting history older than 365 days, reports and daily activity records older than 90 days, and poll options older than 30 days. The operator must schedule it. Backups have a separate retention schedule controlled by the operator.")
                Text("The app keeps a limited offline copy on this device with iOS file protection, excluded from backups. It expires after seven days and is removed on logout. Exports you save or share are under your control.")
                Text("We record daily registration, activity, connection and voting events for aggregate service metrics. We do not collect contacts, location or photos. There is no advertising SDK.")
            }
            Section("Notifications and points") {
                Text("An optional daily reminder is scheduled on this device. It does not mean you have received a new compliment. Remote push notifications are not available. Coins are participation points with no cash value.")
            }
            Section("Community guidelines") {
                Text("Do not harass others, impersonate someone or submit sensitive information in your nickname. Reports are reviewed by the service operator, not automatically. Review times depend on the operator.")
                Text("Privacy information version: \(PrivacyPolicy.version)").font(.caption)
            }
        }.navigationTitle("Privacy information")
    }
}

struct ConsentView: View {
    @EnvironmentObject var auth: AuthViewModel
    var body: some View {
        NavigationView {
            VStack {
                PrivacyView()
                Button("Accept and Continue") {
                    Task { await auth.perform("/v1/consent", body: ["consent": true, "consentVersion": PrivacyPolicy.version]) }
                }.buttonStyle(.borderedProminent).disabled(auth.isBusy).padding()
                Button("Log Out") { Task { await auth.signOut() } }.disabled(auth.isBusy)
                NavigationLink("Export or delete my account") { AccountDataView() }.padding(.bottom)
            }
        }.navigationViewStyle(.stack)
    }
}
