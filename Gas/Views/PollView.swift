//
//  PollView.swift
//  Gas
//
//  Created by Gas Team
//

import SwiftUI

struct PollView: View {
    @StateObject private var viewModel = PollViewModel()
    @State private var selectedOption: String? = nil
    @State private var showCongrats = false
    
    var body: some View {
        ZStack {
            if let poll = viewModel.currentPoll {
                pollBackground(for: poll)
                
                VStack(spacing: 0) {
                    // Header
                    HStack {
                        Text("Inbox")
                            .foregroundColor(.gray.opacity(0.7))
                        Spacer()
                        Text("Gas")
                            .fontWeight(.bold)
                        Spacer()
                        Text("Profile")
                            .foregroundColor(.gray.opacity(0.7))
                    }
                    .foregroundColor(.white)
                    .padding()
                    
                    // Progress
                    Text("\(viewModel.currentIndex + 1) of \(viewModel.totalPolls)")
                        .foregroundColor(.white)
                        .padding(.top, 10)
                    
                    Spacer()
                    
                    // Poll Content
                    VStack(spacing: 40) {
                        // Emoji
                        Text(poll.emoji)
                            .font(.system(size: 100))
                        
                        // Question
                        Text(poll.question)
                            .font(.title)
                            .fontWeight(.semibold)
                            .foregroundColor(.white)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                        
                        Spacer().frame(height: 40)
                        
                        // Options Grid
                        VStack(spacing: 15) {
                            HStack(spacing: 15) {
                                optionButton(poll.options[0])
                                optionButton(poll.options[1])
                            }
                            HStack(spacing: 15) {
                                optionButton(poll.options[2])
                                optionButton(poll.options[3])
                            }
                        }
                        .padding(.horizontal, 40)
                    }
                    
                    Spacer()
                    
                    // Bottom Controls
                    HStack {
                        Button(action: viewModel.shuffleOptions) {
                            HStack {
                                Image(systemName: "shuffle")
                                Text("Shuffle")
                            }
                            .foregroundColor(.white)
                        }
                        
                        Spacer()
                        
                        Button(action: viewModel.skipPoll) {
                            HStack {
                                Image(systemName: "forward.fill")
                                Text("Skip")
                            }
                            .foregroundColor(.white)
                        }
                    }
                    .padding(.horizontal, 40)
                    .padding(.bottom, 40)
                }
            }
            
            if showCongrats {
                CongratsView(coins: viewModel.coinsEarned) {
                    showCongrats = false
                    viewModel.nextPoll()
                }
            }
        }
        .onAppear {
            viewModel.loadPolls()
        }
    }
    
    func pollBackground(for poll: Poll) -> some View {
        LinearGradient(
            colors: backgroundColors(for: poll.backgroundColor),
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
        .ignoresSafeArea()
    }
    
    func backgroundColors(for colorName: String) -> [Color] {
        switch colorName {
        case "brown":
            return [Color.brown.opacity(0.8), Color.brown.opacity(0.6)]
        case "blue":
            return [Color.cyan.opacity(0.7), Color.cyan.opacity(0.5)]
        case "purple":
            return [Color.purple.opacity(0.7), Color.purple.opacity(0.5)]
        default:
            return [Color.orange.opacity(0.7), Color.orange.opacity(0.5)]
        }
    }
    
    func optionButton(_ option: Poll.PollOption) -> some View {
        Button(action: {
            selectedOption = option.id
            submitVote(for: option)
        }) {
            Text(option.userName)
                .font(.headline)
                .foregroundColor(.black)
                .frame(maxWidth: .infinity)
                .padding()
                .background(
                    RoundedRectangle(cornerRadius: 15)
                        .fill(Color.white)
                        .opacity(selectedOption == option.id ? 0.7 : 1.0)
                )
        }
    }
    
    func submitVote(for option: Poll.PollOption) {
        viewModel.submitResponse(selectedUserId: option.userId)
        
        // Show animation
        withAnimation(.easeInOut(duration: 0.3)) {
            selectedOption = option.id
        }
        
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            selectedOption = nil
            showCongrats = true
        }
    }
}

struct CongratsView: View {
    let coins: Int
    let onDismiss: () -> Void
    
    var body: some View {
        ZStack {
            Color.black.opacity(0.3)
                .ignoresSafeArea()
                .onTapGesture {
                    onDismiss()
                }
            
            VStack(spacing: 20) {
                Text("Congrats")
                    .font(.system(size: 40, weight: .bold))
                
                HStack(spacing: 10) {
                    Image(systemName: "dollarsign.circle.fill")
                        .font(.system(size: 60))
                        .foregroundColor(.yellow)
                    Image(systemName: "dollarsign.circle.fill")
                        .font(.system(size: 50))
                        .foregroundColor(.yellow)
                }
                
                Text("You earned \(coins) coins")
                    .font(.title2)
                    .fontWeight(.semibold)
                
                Button(action: onDismiss) {
                    HStack {
                        Image(systemName: "dollarsign.circle.fill")
                            .foregroundColor(.yellow)
                        Text("Cash Out")
                            .fontWeight(.semibold)
                    }
                    .foregroundColor(.black)
                    .frame(width: 200)
                    .padding()
                    .background(Color.white)
                    .cornerRadius(25)
                }
                .padding(.top, 20)
            }
            .padding(40)
            .background(Color.white)
            .cornerRadius(20)
        }
    }
}
