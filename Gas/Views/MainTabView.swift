import SwiftUI

struct MainTabView: View {
    @EnvironmentObject var auth: AuthViewModel
    @Environment(\.scenePhase) private var scenePhase
    var body: some View {
        TabView {
            PollView().tabItem { Label("Polls", systemImage: "flame.fill") }
            InboxView().tabItem { Label("Inbox", systemImage: "tray.fill") }
                .badge(auth.unreadCount)
            FriendsView().tabItem { Label("Friends", systemImage: "person.2.fill") }
                .badge(auth.requests.count)
            ProfileView().tabItem { Label("Profile", systemImage: "person.crop.circle") }
        }
        .tint(.orange)
        .safeAreaInset(edge: .top) {
            if auth.isOffline || auth.status != nil {
                Text(auth.isOffline ? "Offline · Showing saved data. Reconnect to make changes." : (auth.status ?? ""))
                    .font(.caption).frame(maxWidth: .infinity).padding(8).background(.regularMaterial)
            }
        }
        .task(id: scenePhase) {
            guard scenePhase == .active else { return }
            while !Task.isCancelled {
                await auth.refresh(preserveInbox: true)
                do { try await Task.sleep(nanoseconds: 30_000_000_000) }
                catch { return }
            }
        }
    }
}
