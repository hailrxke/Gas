//
//  AuthViewModel.swift
//  Gas
//
//  Created by Gas Team
//

import Foundation
import Combine

class AuthViewModel: ObservableObject {
    @Published var isAuthenticated = false
    @Published var currentUser: User?
    
    func completeOnboarding() {
        // In production, this would handle actual authentication
        isAuthenticated = true
    }
    
    func signOut() {
        isAuthenticated = false
        currentUser = nil
    }
}
