import SwiftUI

struct AgeVerificationView: View {
    @Binding var birthDate: Date
    var body: some View {
        DatePicker("Date of birth", selection: $birthDate, in: ...Date(), displayedComponents: .date)
        Text("For students ages 14–19. Your date of birth is private and is not shown to other students.")
            .font(.footnote).foregroundColor(.secondary)
    }
    static func value(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: date)
    }
}
