import SwiftUI

struct ContentView: View {
    @EnvironmentObject var authViewModel: AuthViewModel
    var body: some View {
        Group {
            if authViewModel.isRestoring {
                ProgressView("Connecting to GAS…")
            } else if authViewModel.isAuthenticated {
                MainTabView()
            } else {
                OnboardingFlow()
            }
        }
        .task { await authViewModel.restore() }
        .alert("Something went wrong", isPresented: Binding(get: { authViewModel.error != nil }, set: { if !$0 { authViewModel.error = nil } })) {
            Button("OK") { authViewModel.error = nil }
        } message: { Text(authViewModel.error ?? "") }
    }
}
