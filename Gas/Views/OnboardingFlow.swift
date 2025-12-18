//
//  OnboardingFlow.swift
//  Gas
//
//  Created by Gas Team
//

import SwiftUI

struct OnboardingFlow: View {
    @State private var currentStep: OnboardingStep = .splash
    @EnvironmentObject var authViewModel: AuthViewModel
    
    enum OnboardingStep {
        case splash
        case ageVerification
        case schoolLocation
        case gradeSelection
        case schoolSearch
        case phoneNumber
        case verification
        case name
        case username
        case gender
        case profilePhoto
        case addFriends
        case notifications
        case welcome
    }
    
    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            
            switch currentStep {
            case .splash:
                SplashView(onComplete: { currentStep = .ageVerification })
            case .ageVerification:
                AgeVerificationView(onNext: { currentStep = .schoolLocation })
            case .schoolLocation:
                SchoolLocationView(onNext: { currentStep = .gradeSelection })
            case .gradeSelection:
                GradeSelectionView(onNext: { currentStep = .schoolSearch })
            case .schoolSearch:
                SchoolSearchView(onNext: { currentStep = .phoneNumber })
            case .phoneNumber:
                PhoneNumberView(onNext: { currentStep = .verification })
            case .verification:
                VerificationView(onNext: { currentStep = .name })
            case .name:
                NameInputView(onNext: { currentStep = .username })
            case .username:
                UsernameView(onNext: { currentStep = .gender })
            case .gender:
                GenderSelectionView(onNext: { currentStep = .profilePhoto })
            case .profilePhoto:
                ProfilePhotoView(onNext: { currentStep = .addFriends })
            case .addFriends:
                AddFriendsView(onNext: { currentStep = .notifications })
            case .notifications:
                NotificationsPermissionView(onNext: { currentStep = .welcome })
            case .welcome:
                WelcomeView(onComplete: { authViewModel.completeOnboarding() })
            }
        }
    }
}
