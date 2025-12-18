# Gas - iOS Social Polling App

Gas is a social polling app for high school students in Korea, where friends answer anonymous polls about each other and receive notifications when they're picked.

## Features

- **Age Verification**: Users must verify their age before accessing the app
- **School-based Connection**: Find and connect with classmates by selecting your school
- **Phone Verification**: SMS-based authentication
- **User Profile**: Create profile with photo, name, username, and gender
- **Friend Management**: Add friends from contacts and mutual connections
- **Poll System**: Answer fun poll questions about your friends
  - Multiple choice polls with 4 friend options
  - Various question categories (e.g., "Best person to go camping with", "Smiling 24/7")
  - Shuffle and skip options
  - Track poll progress (e.g., "1 of 12")
- **Flame Notifications**: Get notified when friends pick you ("A girl gassed you up" with flame emoji)
- **Coin Rewards**: Earn coins for participating in polls
- **Cash Out**: Redeem earned coins
- **Three Tab Interface**:
  - Inbox: View notifications and flames
  - Gas: Main polling interface
  - Profile: User settings and information

## Design

- **Colors**: 
  - Primary: Orange/Coral (#FF6347)
  - Secondary: Light blue, brown tones for polls
  - Background: Dark for splash screen, light for main app
- **Logo**: "GAS" with flame-styled letters
- **UI**: Clean, modern iOS design with rounded buttons and card-based layouts

## Technology Stack

- SwiftUI for iOS
- Firebase for authentication and backend
- CoreLocation for school proximity detection
- Contacts framework for friend suggestions
- Push notifications for engagement

## Setup

1. Open Gas.xcodeproj in Xcode 14+
2. Configure Firebase credentials
3. Run on iOS 15+ device or simulator

## Privacy

Gas prioritizes user privacy:
- Location is only used to find nearby schools
- Contacts are used only for friend suggestions
- All data is encrypted and secure
