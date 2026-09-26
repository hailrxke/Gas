import SwiftUI

struct ContentView: View {
    @EnvironmentObject var authViewModel: AuthViewModel
    var body: some View {
        Group {
            if authViewModel.isRestoring {
                ProgressView("Connecting to GAS…")
            } else if authViewModel.isAuthenticated {
                if authViewModel.needsConsent { ConsentView() }
                else { MainTabView() }
            } else {
                OnboardingFlow()
            }
        }
        .task { await authViewModel.restore() }
        .sheet(isPresented: Binding(get: { authViewModel.recoveryCode != nil }, set: { if !$0 { authViewModel.recoveryCode = nil } })) {
            RecoveryCodeView(code: authViewModel.recoveryCode ?? "")
        }
        .alert("Something went wrong", isPresented: Binding(get: { authViewModel.error != nil }, set: { if !$0 { authViewModel.error = nil } })) {
            Button("OK") { authViewModel.error = nil }
        } message: { Text(authViewModel.error ?? "") }
    }
}
