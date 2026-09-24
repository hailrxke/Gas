import SwiftUI

struct AgeVerificationView: View {
    @Binding var age: Int
    var body: some View {
        Picker("Age", selection: $age) {
            ForEach(14...19, id: \.self) { value in
                Text("\(value) years old").tag(value)
            }
        }
        Text("This MVP is for students ages 14–19.")
            .font(.footnote)
            .foregroundColor(.secondary)
    }
}
