import SwiftUI

struct PrivacyView: View {
    var body: some View {
        List {
            Section(header: Text("Information we store")) {
                Text("We store your username, name or nickname, age, school name, friendships, votes, and reports on the server. Passwords are stored as verification hashes, never as plain text.")
            }
            Section(header: Text("Who can see your information?")) {
                Text("People who entered the same school name can find your profile by searching for your exact username. You must accept a friend request before you can vote about each other.")
                Text("Recipients do not receive the voter’s name. With only a few friends, they may still be able to guess who voted. The server operator manages voting records to run the service and handle reports.")
            }
            Section(header: Text("Managing your information")) {
                Text("You can remove or block people in the Friends tab. Deleting your account removes your account, sessions, related votes, and friendships from the server. If the operator maintains backups, their backup retention policy also applies.")
                Text("We do not collect contacts, location, or photos. Push notifications and cash withdrawals are not available. Coins are participation points within the app.")
            }
            Section(header: Text("Community guidelines")) {
                Text("Do not impersonate or harass others. You can report unwanted compliments and block their sender from your inbox. Reports are recorded on the server and are not reviewed automatically.")
            }
        }.navigationTitle("Privacy information")
    }
}
