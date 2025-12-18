//
//  OnboardingViews.swift
//  Gas
//
//  Created by Gas Team
//
//  Placeholder views for onboarding flow

import SwiftUI

// MARK: - School Location View
struct SchoolLocationView: View {
    let onNext: () -> Void
    
    var body: some View {
        ZStack {
            Color.orange.ignoresSafeArea()
            
            VStack(spacing: 40) {
                Image(systemName: "map")
                    .font(.system(size: 100))
                    .foregroundColor(.white)
                
                Text("Connect your school\nto find friends")
                    .font(.title)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                    .multilineTextAlignment(.center)
                
                Button(action: onNext) {
                    HStack {
                        Image(systemName: "location")
                        Text("Find My School")
                    }
                    .font(.headline)
                    .foregroundColor(.orange)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.white)
                    .cornerRadius(25)
                }
                .padding(.horizontal, 40)
            }
        }
    }
}

// MARK: - Grade Selection View
struct GradeSelectionView: View {
    let onNext: () -> Void
    @State private var selectedGrade: String = "Grade 10"
    
    var body: some View {
        ZStack {
            Color.orange.ignoresSafeArea()
            
            VStack {
                Text("What grade are you in?")
                    .font(.title2)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                    .padding(.top, 100)
                
                ScrollView {
                    VStack(spacing: 0) {
                        ForEach(["Not in High School", "Grade 9", "Grade 10", "Grade 11", "Grade 12", "Finished High School"], id: \.self) { grade in
                            Button(action: {
                                selectedGrade = grade
                                onNext()
                            }) {
                                HStack {
                                    Text(grade)
                                        .foregroundColor(.black)
                                    Spacer()
                                    if grade.contains("Grade") {
                                        Text("CLASS OF 2026")
                                            .font(.caption)
                                            .foregroundColor(.gray)
                                    }
                                }
                                .padding()
                                .background(Color.white)
                            }
                            Divider()
                        }
                    }
                }
                .background(Color.white)
                .cornerRadius(20)
                .padding()
                
                Spacer()
            }
        }
    }
}

// MARK: - School Search View
struct SchoolSearchView: View {
    let onNext: () -> Void
    
    var body: some View {
        ZStack {
            Color.orange.ignoresSafeArea()
            
            VStack {
                Text("Pick your school")
                    .font(.title2)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                    .padding(.top, 60)
                
                TextField("Search...", text: .constant(""))
                    .padding()
                    .background(Color.white)
                    .cornerRadius(10)
                    .padding()
                
                Button(action: onNext) {
                    Text("Can't find my school")
                        .foregroundColor(.white)
                }
                
                Spacer()
            }
        }
    }
}

// MARK: - Phone Number View
struct PhoneNumberView: View {
    let onNext: () -> Void
    @State private var phoneNumber = ""
    
    var body: some View {
        ZStack {
            Color.orange.ignoresSafeArea()
            
            VStack(spacing: 30) {
                Spacer()
                
                Text("Enter your phone number")
                    .font(.title2)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                
                HStack {
                    Text("🇺🇸 +1")
                        .font(.title3)
                    Text(phoneNumber.isEmpty ? "" : phoneNumber)
                        .font(.title3)
                        .foregroundColor(.white)
                }
                
                Text("Remember - never sign up\nwith another person's phone number.")
                    .font(.subheadline)
                    .foregroundColor(.white.opacity(0.8))
                    .multilineTextAlignment(.center)
                
                Spacer()
                
                Button(action: onNext) {
                    Text("Next")
                        .font(.headline)
                        .foregroundColor(.orange)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.white)
                        .cornerRadius(25)
                }
                .padding(.horizontal, 40)
                .padding(.bottom, 40)
            }
        }
    }
}

// MARK: - Verification View
struct VerificationView: View {
    let onNext: () -> Void
    
    var body: some View {
        ZStack {
            Color.orange.ignoresSafeArea()
            
            VStack {
                Spacer()
                
                Text("We sent you a code to verify\nyour number")
                    .font(.title2)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                    .multilineTextAlignment(.center)
                
                Text("Sent to +1 628-267-9041")
                    .foregroundColor(.white.opacity(0.8))
                    .padding(.top, 5)
                
                TextField("Code", text: .constant(""))
                    .font(.title3)
                    .foregroundColor(.white)
                    .padding()
                    .padding(.top, 30)
                
                Text("Resend in 28")
                    .foregroundColor(.white)
                    .padding(.top, 20)
                
                Spacer()
                
                Button(action: onNext) {
                    Text("Next")
                        .font(.headline)
                        .foregroundColor(.orange)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.white)
                        .cornerRadius(25)
                }
                .padding(.horizontal, 40)
                .padding(.bottom, 40)
            }
        }
    }
}

// MARK: - Name Input View
struct NameInputView: View {
    let onNext: () -> Void
    @State private var firstName = ""
    
    var body: some View {
        ZStack {
            Color.orange.ignoresSafeArea()
            
            VStack {
                Spacer()
                
                Text("What's your first name?")
                    .font(.title2)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                
                TextField("First Name", text: $firstName)
                    .font(.title)
                    .foregroundColor(.white)
                    .multilineTextAlignment(.center)
                    .padding()
                
                Spacer()
                
                Button(action: onNext) {
                    Text("Next")
                        .font(.headline)
                        .foregroundColor(.orange)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.white)
                        .cornerRadius(25)
                }
                .padding(.horizontal, 40)
                .padding(.bottom, 40)
            }
        }
    }
}

// MARK: - Username View
struct UsernameView: View {
    let onNext: () -> Void
    @State private var username = ""
    
    var body: some View {
        ZStack {
            Color.orange.ignoresSafeArea()
            
            VStack {
                Spacer()
                
                Text("Choose a username")
                    .font(.title2)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                
                TextField("username", text: $username)
                    .font(.title)
                    .foregroundColor(.white)
                    .multilineTextAlignment(.center)
                    .padding()
                
                Spacer()
                
                Button(action: onNext) {
                    Text("Next")
                        .font(.headline)
                        .foregroundColor(.orange)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.white)
                        .cornerRadius(25)
                }
                .padding(.horizontal, 40)
                .padding(.bottom, 40)
            }
        }
    }
}

// MARK: - Gender Selection View
struct GenderSelectionView: View {
    let onNext: () -> Void
    
    var body: some View {
        ZStack {
            Color.orange.ignoresSafeArea()
            
            VStack(spacing: 40) {
                Text("What's your gender?")
                    .font(.title2)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                    .padding(.top, 100)
                
                VStack(spacing: 20) {
                    genderButton(emoji: "👦", label: "Boy")
                    genderButton(emoji: "👧", label: "Girl")
                    genderButton(emoji: "🧑", label: "Non-binary")
                }
                .padding(.horizontal, 60)
                
                Spacer()
            }
        }
    }
    
    func genderButton(emoji: String, label: String) -> some View {
        Button(action: onNext) {
            VStack(spacing: 15) {
                Text(emoji)
                    .font(.system(size: 60))
                Text(label)
                    .font(.headline)
                    .foregroundColor(.white)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 30)
            .background(Color.orange.opacity(0.3))
            .cornerRadius(20)
        }
    }
}

// MARK: - Profile Photo View
struct ProfilePhotoView: View {
    let onNext: () -> Void
    
    var body: some View {
        ZStack {
            Color.orange.ignoresSafeArea()
            
            VStack(spacing: 40) {
                Text("Add a profile photo")
                    .font(.title2)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                    .padding(.top, 100)
                
                ZStack {
                    Circle()
                        .fill(Color.white.opacity(0.3))
                        .frame(width: 200, height: 200)
                    
                    Image(systemName: "person.fill")
                        .font(.system(size: 80))
                        .foregroundColor(.white.opacity(0.5))
                    
                    Circle()
                        .fill(Color.orange)
                        .frame(width: 50, height: 50)
                        .overlay(
                            Image(systemName: "plus")
                                .foregroundColor(.white)
                        )
                        .offset(x: 70, y: 70)
                }
                
                Text("Add a photo so your friends\ncan find you")
                    .font(.subheadline)
                    .foregroundColor(.white.opacity(0.8))
                    .multilineTextAlignment(.center)
                
                Spacer()
                
                VStack(spacing: 15) {
                    Button(action: {}) {
                        Text("Choose a photo")
                            .font(.headline)
                            .foregroundColor(.orange)
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color.white)
                            .cornerRadius(25)
                    }
                    
                    Button(action: {}) {
                        Text("Take a photo")
                            .font(.headline)
                            .foregroundColor(.orange)
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color.white)
                            .cornerRadius(25)
                    }
                }
                .padding(.horizontal, 40)
                
                Button(action: onNext) {
                    Text("Skip")
                        .foregroundColor(.white)
                        .padding()
                }
            }
        }
    }
}

// MARK: - Add Friends View
struct AddFriendsView: View {
    let onNext: () -> Void
    
    var body: some View {
        ZStack {
            Color.orange.ignoresSafeArea()
            
            VStack {
                HStack {
                    Spacer()
                    Button(action: onNext) {
                        Text("Next")
                            .foregroundColor(.white)
                            .padding()
                    }
                }
                
                Text("Add Friends")
                    .font(.title)
                    .fontWeight(.bold)
                    .foregroundColor(.white)
                
                Text("PEOPLE YOU MAY KNOW")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.6))
                    .padding(.top)
                
                ScrollView {
                    VStack(spacing: 15) {
                        ForEach(0..<5) { _ in
                            HStack {
                                Circle()
                                    .fill(Color.gray)
                                    .frame(width: 50, height: 50)
                                
                                VStack(alignment: .leading) {
                                    Text("Friend Name")
                                        .foregroundColor(.white)
                                    Text("1 mutual friends")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.6))
                                }
                                
                                Spacer()
                                
                                Circle()
                                    .stroke(Color.white, lineWidth: 2)
                                    .frame(width: 30, height: 30)
                            }
                            .padding()
                        }
                    }
                }
                .padding()
            }
        }
    }
}

// MARK: - Notifications Permission View
struct NotificationsPermissionView: View {
    let onNext: () -> Void
    
    var body: some View {
        ZStack {
            Color.black.opacity(0.8).ignoresSafeArea()
            
            VStack(spacing: 40) {
                Text("GAS WORKS\nBEST WITH\nNOTIFICATIONS ON")
                    .font(.title)
                    .fontWeight(.bold)
                    .foregroundColor(.white)
                    .multilineTextAlignment(.center)
                
                Image(systemName: "hand.point.down.fill")
                    .font(.system(size: 60))
                    .foregroundColor(.yellow)
                
                Button(action: onNext) {
                    Text("Allow")
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(width: 250)
                        .padding()
                        .background(Color.blue)
                        .cornerRadius(15)
                }
            }
        }
    }
}

// MARK: - Welcome View
struct WelcomeView: View {
    let onComplete: () -> Void
    
    var body: some View {
        ZStack {
            Color.white.ignoresSafeArea()
            
            VStack(spacing: 30) {
                Text("WELCOME TO")
                    .font(.title)
                    .fontWeight(.bold)
                
                Text("GAS")
                    .font(.system(size: 70, weight: .bold))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [Color.orange, Color.yellow],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                
                HStack(spacing: 40) {
                    VStack {
                        RoundedRectangle(cornerRadius: 20)
                            .fill(Color.purple)
                            .frame(width: 140, height: 200)
                            .overlay(
                                VStack {
                                    Text("😁")
                                        .font(.system(size: 50))
                                    Text("BEST SMILE")
                                        .font(.caption)
                                        .fontWeight(.bold)
                                        .foregroundColor(.white)
                                }
                            )
                        
                        Text("Answer Polls\nAbout Friends")
                            .font(.caption)
                            .fontWeight(.semibold)
                            .multilineTextAlignment(.center)
                    }
                    
                    VStack {
                        RoundedRectangle(cornerRadius: 20)
                            .fill(Color.white)
                            .frame(width: 140, height: 200)
                            .overlay(
                                VStack(spacing: 20) {
                                    Text("👧 A girl gassed you up")
                                        .font(.caption2)
                                        .multilineTextAlignment(.center)
                                    Text("🔥")
                                        .font(.system(size: 60))
                                }
                            )
                            .shadow(radius: 5)
                        
                        Text("Get Flames\nWhen Picked")
                            .font(.caption)
                            .fontWeight(.semibold)
                            .multilineTextAlignment(.center)
                    }
                }
                
                Button(action: onComplete) {
                    Text("Start")
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.orange)
                        .cornerRadius(25)
                }
                .padding(.horizontal, 40)
                .padding(.top, 30)
            }
        }
    }
}

// MARK: - Inbox View
struct InboxView: View {
    var body: some View {
        NavigationView {
            VStack {
                Text("Inbox")
                    .font(.title)
                    .fontWeight(.bold)
                
                Text("Your flames will appear here")
                    .foregroundColor(.gray)
                    .padding()
                
                Spacer()
            }
            .navigationBarHidden(true)
        }
    }
}

// MARK: - Profile View
struct ProfileView: View {
    var body: some View {
        NavigationView {
            VStack {
                Text("Profile")
                    .font(.title)
                    .fontWeight(.bold)
                    .padding()
                
                Circle()
                    .fill(Color.gray.opacity(0.3))
                    .frame(width: 100, height: 100)
                    .overlay(
                        Image(systemName: "person.fill")
                            .font(.system(size: 50))
                            .foregroundColor(.gray)
                    )
                
                Text("Your Name")
                    .font(.title2)
                    .fontWeight(.semibold)
                    .padding(.top)
                
                Text("@username")
                    .foregroundColor(.gray)
                
                Spacer()
            }
            .navigationBarHidden(true)
        }
    }
}
