//
//  User.swift
//  Gas
//
//  Created by Gas Team
//

import Foundation

struct User: Identifiable, Codable {
    let id: String
    var phoneNumber: String
    var firstName: String
    var lastName: String
    var username: String
    var gender: Gender
    var age: Int
    var school: School?
    var profilePhotoURL: String?
    var coins: Int
    var friends: [String] // User IDs
    
    enum Gender: String, Codable {
        case boy
        case girl
        case nonBinary
    }
}
