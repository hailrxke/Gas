//
//  School.swift
//  Gas
//
//  Created by Gas Team
//

import Foundation
import CoreLocation

struct School: Identifiable, Codable {
    let id: String
    var name: String
    var location: String
    var memberCount: Int
    var logoURL: String?
    
    var coordinate: CLLocationCoordinate2D? {
        // Would be populated from geocoding or database
        nil
    }
}
