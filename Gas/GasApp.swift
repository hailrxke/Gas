//
//  GasApp.swift
//  Gas
//
//  Created by Gas Team
//

import SwiftUI

@main
struct GasApp: App {
    @StateObject private var authViewModel = AuthViewModel()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(authViewModel)
        }
    }
}
