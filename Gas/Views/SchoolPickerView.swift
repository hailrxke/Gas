import SwiftUI

struct SchoolPickerView: View {
    @EnvironmentObject var auth: AuthViewModel
    @Environment(\.dismiss) private var dismiss
    @Binding var selection: School?
    @State private var query = ""
    @State private var schools: [School] = []
    @State private var loading = false
    @State private var message: String?

    var body: some View {
        List {
            if loading { ProgressView("Finding schools…") }
            if let message = message { Text(message).foregroundColor(.secondary) }
            ForEach(schools) { school in
                Button {
                    selection = school
                    dismiss()
                } label: {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(school.displayName).foregroundColor(.primary)
                        if !school.englishName.isEmpty { Text(school.name).font(.caption) }
                        Text([school.region, school.address].filter { !$0.isEmpty }.joined(separator: " · "))
                            .font(.caption).foregroundColor(.secondary)
                        if selection?.id == school.id { Label("Selected", systemImage: "checkmark") }
                    }
                }
            }
            Text("Choose the same school as your friends. Selecting a school does not verify enrollment. If your school is missing, contact the service operator.")
                .font(.footnote).foregroundColor(.secondary)
        }
        .navigationTitle("Choose School")
        .searchable(text: $query, prompt: "School name or region")
        .task(id: query) {
            loading = true; message = nil
            do {
                try await Task.sleep(nanoseconds: 300_000_000)
                let result: SchoolsResult = try await auth.api.request(APIClient.path("/v1/schools", query: ["q": query]))
                try Task.checkCancellation()
                schools = result.schools
                if schools.isEmpty { message = "No schools found. Try a different name or region." }
                loading = false
            } catch {
                guard !Task.isCancelled else { return }
                schools = []; message = error.localizedDescription; loading = false
            }
        }
    }
}
