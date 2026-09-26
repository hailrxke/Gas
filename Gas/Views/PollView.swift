import SwiftUI

struct PollView: View {
    @EnvironmentObject var auth: AuthViewModel
    @StateObject private var model = PollViewModel()
    var body: some View {
        NavigationView {
            ZStack {
                LinearGradient(colors: [.orange, .pink.opacity(0.8)], startPoint: .topLeading, endPoint: .bottomTrailing)
                    .ignoresSafeArea()
                ScrollView {
                    VStack(spacing: 26) {
                        Text("Today: \(model.answered) / \(model.totalPolls)")
                            .font(.headline)
                        if model.isLoading {
                            ProgressView("Loading polls…")
                        } else if let poll = model.currentPoll {
                            Text(poll.emoji).font(.system(size: 80))
                            Text(poll.question)
                                .font(.largeTitle.bold())
                                .multilineTextAlignment(.center)
                            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 16) {
                                ForEach(poll.options) { option in
                                    Button {
                                        Task { await model.submit(option, auth: auth) }
                                    } label: {
                                        Text(option.userName)
                                            .font(.headline)
                                            .foregroundColor(.primary)
                                            .frame(maxWidth: .infinity, minHeight: 72)
                                            .background(.regularMaterial)
                                            .cornerRadius(18)
                                    }
                                    .disabled(model.isSubmitting || model.coinsEarned != nil)
                                }
                            }
                            if model.isSubmitting { ProgressView("Sending…") }
                            HStack {
                                Button("Change options") { Task { await model.change("shuffle", auth: auth) } }
                                    .disabled(model.friendCount <= 4)
                                Spacer()
                                Button("Skip") { Task { await model.change("skip", auth: auth) } }
                            }.disabled(model.isSubmitting || model.coinsEarned != nil)
                        } else {
                            Image(systemName: model.answered == model.totalPolls ? "checkmark.circle.fill" : "person.2.fill")
                                .font(.system(size: 64))
                            Text(model.answered == model.totalPolls ? "You’ve finished today’s polls!" : (model.skipped > 0 ? "You’ve skipped the remaining polls" : "Connect with at least \(model.minimumFriends) friends"))
                                .font(.title2.bold())
                            Text(model.answered == model.totalPolls ? "Polls reopen at midnight Korea time." : "Find schoolmates in Friends and accept each other’s request. You have \(model.friendCount) accepted friends.")
                                .multilineTextAlignment(.center)
                        }
                        if model.skipped > 0 {
                            Button("Restore skipped polls (\(model.skipped))") { Task { await model.change("restore", auth: auth) } }
                                .disabled(model.isSubmitting || model.isLoading)
                        }
                        if let error = model.error {
                            Text(error).font(.footnote)
                        }
                        Button("Refresh") { model.error = nil; Task { await model.load(auth) } }
                            .disabled(model.isLoading || model.isSubmitting)
                    }.padding(24)
                }.foregroundColor(.white)
            }
            .navigationTitle("🔥 GAS")
            .navigationBarTitleDisplayMode(.inline)
            .task { await model.load(auth) }
            .refreshable { await model.load(auth) }
            .alert("Thanks!", isPresented: Binding(get: { model.coinsEarned != nil }, set: { if !$0 { model.coinsEarned = nil } })) {
                Button("Continue") { model.coinsEarned = nil }
            } message: {
                Text("You earned \(model.coinsEarned ?? 0) coins. Coins are participation points and cannot be exchanged for cash.")
            }
        }.navigationViewStyle(.stack)
    }
}
