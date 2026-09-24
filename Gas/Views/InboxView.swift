import SwiftUI

struct InboxView: View {
    @EnvironmentObject var auth: AuthViewModel
    @State private var reporting: Flame?
    @State private var reason = ""

    var body: some View {
        NavigationView {
            List {
                if auth.flames.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("No compliments yet").font(.headline)
                        Text("When a friend picks you, their compliment will appear here. Pull down to refresh.")
                            .foregroundColor(.secondary)
                    }.padding(.vertical)
                }
                ForEach(auth.flames) { flame in
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Text("🔥 A friend picked you").font(.headline)
                            if !flame.isRead { Circle().fill(.orange).frame(width: 8, height: 8).accessibilityLabel("Unread") }
                        }
                        Text(flame.pollQuestion).font(.title3)
                        Text(flame.day).font(.caption).foregroundColor(.secondary)
                        HStack {
                            if !flame.isRead {
                                Button("Mark as read") { Task { await auth.perform("/v1/inbox/read", body: ["id": flame.id]) } }
                            }
                            Spacer()
                            Button("Report & Block", role: .destructive) { reporting = flame; reason = "" }
                        }.font(.caption).buttonStyle(.borderless).disabled(auth.isBusy)
                    }.padding(.vertical, 8)
                }
            }
            .navigationTitle("Inbox")
            .refreshable { await auth.refresh() }
            .task { await auth.refresh() }
            .sheet(item: $reporting) { flame in
                NavigationView {
                    Form {
                        if let error = auth.error { Text(error).foregroundColor(.red) }
                        Text("We will record your report and hide compliments from this sender. Their identity will not be shown.")
                        TextField("Reason for reporting (at least 3 characters)", text: $reason)
                        Button("Report & Block", role: .destructive) {
                            Task {
                                if await auth.perform("/v1/reports", body: ["id": flame.id, "reason": reason]) { reporting = nil }
                            }
                        }.disabled(reason.trimmingCharacters(in: .whitespacesAndNewlines).count < 3 || reason.count > 500 || auth.isBusy)
                    }
                    .navigationTitle("Report")
                    .toolbar { Button("Cancel") { reporting = nil } }
                }
            }
        }.navigationViewStyle(.stack)
    }
}
