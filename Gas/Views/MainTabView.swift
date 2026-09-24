import SwiftUI

struct MainTabView: View {
    @EnvironmentObject var auth: AuthViewModel
    @Environment(\.scenePhase) private var scenePhase
    var body: some View {
        TabView {
            PollView().tabItem { Label("Polls", systemImage: "flame.fill") }
            InboxView().tabItem { Label("Inbox", systemImage: "tray.fill") }
                .badge(auth.flames.filter { !$0.isRead }.count)
            FriendsView().tabItem { Label("Friends", systemImage: "person.2.fill") }
                .badge(auth.requests.count)
            ProfileView().tabItem { Label("Profile", systemImage: "person.crop.circle") }
        }
        .tint(.orange)
        .task { await auth.refresh() }
        .onChange(of: scenePhase) { phase in
            if phase == .active { Task { await auth.refresh() } }
        }
    }
}
