//
//  MainTabView.swift
//  Gas
//
//  Created by Gas Team
//

import SwiftUI

struct MainTabView: View {
    @State private var selectedTab = 1
    
    var body: some View {
        TabView(selection: $selectedTab) {
            InboxView()
                .tabItem {
                    Text("Inbox")
                }
                .tag(0)
            
            PollView()
                .tabItem {
                    Text("Gas")
                }
                .tag(1)
            
            ProfileView()
                .tabItem {
                    Text("Profile")
                }
                .tag(2)
        }
        .accentColor(.orange)
    }
}
