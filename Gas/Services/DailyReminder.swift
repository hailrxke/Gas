import Foundation
import UserNotifications

enum DailyReminder {
    static let identifier = "gas.daily-reminder"
    static var enabled: Bool { UserDefaults.standard.bool(forKey: identifier) }
    static func enable() async throws {
        let center = UNUserNotificationCenter.current()
        guard try await center.requestAuthorization(options: [.alert, .sound]) else {
            throw APIError(status: 0, message: "Notifications are disabled. You can allow them in iPhone Settings.")
        }
        let content = UNMutableNotificationContent()
        content.title = "Give a friend a little boost"
        content.body = "Take a moment to check today’s GAS polls."
        content.sound = .default
        var date = DateComponents(); date.hour = 20; date.minute = 0
        let request = UNNotificationRequest(identifier: identifier, content: content, trigger: UNCalendarNotificationTrigger(dateMatching: date, repeats: true))
        try await center.add(request)
        UserDefaults.standard.set(true, forKey: identifier)
    }
    static func disable() {
        UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: [identifier])
        UNUserNotificationCenter.current().removeDeliveredNotifications(withIdentifiers: [identifier])
        UserDefaults.standard.set(false, forKey: identifier)
    }
}
