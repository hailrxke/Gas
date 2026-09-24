import SwiftUI

struct OnboardingFlow: View {
    @EnvironmentObject var auth: AuthViewModel
    @State private var register = false
    @State private var username = ""
    @State private var password = ""
    @State private var confirmation = ""
    @State private var name = ""
    @State private var school = ""
    @State private var age = 16
    @State private var consent = false
    @State private var showServer = false
    @State private var address = APIClient.configuredServer

    private var canSubmit: Bool {
        let usernameValid = username.range(of: "^[a-zA-Z0-9_]{3,24}$", options: .regularExpression) != nil
        return usernameValid && password.count >= 10 && password.count <= 128 &&
            (!register || (!name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
             school.trimmingCharacters(in: .whitespacesAndNewlines).count >= 2 &&
             password == confirmation && consent))
    }

    var body: some View {
        NavigationView {
            Form {
                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("🔥 GAS")
                            .font(.system(size: 46, weight: .heavy, design: .rounded))
                            .foregroundColor(.orange)
                        Text("Give a friend a little boost")
                            .font(.title2.bold())
                        Text("Connect with friends and send anonymous compliments.")
                            .foregroundColor(.secondary)
                    }.padding(.vertical)
                    Picker("Account", selection: $register) {
                        Text("Log In").tag(false)
                        Text("Sign Up").tag(true)
                    }.pickerStyle(.segmented)
                }
                Section(footer: Text("Usernames must be 3–24 letters, numbers, or underscores. Passwords must be 10–128 characters. Password recovery is not available yet, so keep your password safe.")) {
                    TextField("Username", text: $username)
                        .textContentType(.username)
                        .textInputAutocapitalization(.never)
                        .disableAutocorrection(true)
                    SecureField("Password", text: $password)
                        .textContentType(register ? .newPassword : .password)
                    if register {
                        SecureField("Confirm password", text: $confirmation)
                            .textContentType(.newPassword)
                    }
                }
                if register {
                    Section(header: Text("Profile"), footer: Text("Enter your school’s full name exactly as your friends do. School names are self-reported; enrollment is not verified.")) {
                        TextField("Name or nickname", text: $name)
                        TextField("School name", text: $school)
                        AgeVerificationView(age: $age)
                    }
                    Section {
                        NavigationLink("Privacy information") { PrivacyView() }
                        Toggle("I have read the privacy information and agree to create an account and use the service.", isOn: $consent)
                    }
                }
                Section {
                    Button {
                        Task {
                            await auth.authenticate(register: register, username: username, password: password, name: name, school: school, age: age)
                            if auth.isAuthenticated { password = ""; confirmation = "" }
                        }
                    } label: {
                        HStack {
                            Spacer()
                            if auth.isBusy { ProgressView() }
                            Text(register ? "Create Account" : "Log In")
                                .fontWeight(.semibold)
                            Spacer()
                        }
                    }.disabled(!canSubmit || auth.isBusy)
                }
                Section {
                    Button("Server Settings") { showServer = true }
                }
            }
            .navigationBarHidden(true)
            .disabled(auth.isBusy)
            .sheet(isPresented: $showServer) {
                NavigationView {
                    Form {
                        Section(footer: Text("Enter the HTTPS address provided by the service operator. For a local server running on the simulator’s Mac, use http://localhost:8080.")) {
                            TextField("Server address", text: $address)
                                .keyboardType(.URL)
                                .textInputAutocapitalization(.never)
                                .disableAutocorrection(true)
                        }
                        Button("Save") {
                            Task { await auth.configureServer(address); showServer = false }
                        }
                    }
                    .navigationTitle("Server Connection")
                    .toolbar { Button("Close") { showServer = false } }
                }
            }
        }.navigationViewStyle(.stack)
    }
}
