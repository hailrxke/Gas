//
//  AgeVerificationView.swift
//  Gas
//
//  Created by Gas Team
//

import SwiftUI

struct AgeVerificationView: View {
    let onNext: () -> Void
    @State private var selectedAge: Int = 12
    @State private var showButton = false
    
    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            
            VStack(spacing: 30) {
                Spacer()
                
                // Logo
                Text("GAS")
                    .font(.system(size: 70, weight: .bold))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [Color.orange, Color.yellow],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                
                Spacer()
                
                VStack(spacing: 20) {
                    Text("By entering your age you agree to our")
                        .foregroundColor(.gray)
                    Text("Terms and Privacy Policy")
                        .foregroundColor(.gray)
                }
                .font(.subheadline)
                
                Text("Enter your age")
                    .font(.title3)
                    .foregroundColor(.orange)
                    .padding(.top)
                
                // Age Picker
                Picker("Age", selection: $selectedAge) {
                    ForEach(10..<100) { age in
                        Text("\(age)").tag(age)
                    }
                }
                .pickerStyle(.wheel)
                .frame(height: 150)
                .onChange(of: selectedAge) { _ in
                    showButton = selectedAge >= 12
                }
                
                if showButton {
                    Button(action: onNext) {
                        Text("Get Started")
                            .font(.headline)
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color.orange)
                            .cornerRadius(25)
                    }
                    .padding(.horizontal, 40)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                }
                
                Spacer()
                
                // Login
                HStack {
                    Spacer()
                    Text("Log In")
                        .foregroundColor(.white)
                        .padding()
                }
            }
        }
    }
}
