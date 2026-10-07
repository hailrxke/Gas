package app.gas.korea.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

const val CONSENT_VERSION = "2026-09-27"
val WireJson = Json { ignoreUnknownKeys = true; encodeDefaults = true }
fun body(vararg values: Pair<String, Any>): JsonObject = JsonObject(values.associate { (key, value) ->
    key to when (value) {
        is Boolean -> JsonPrimitive(value)
        is Number -> JsonPrimitive(value)
        else -> JsonPrimitive(value.toString())
    }
})

@Serializable data class User(
    val id: String, val username: String, val name: String, val school: String, val schoolId: String,
    val age: Int? = null, val birthDate: String? = null, val coins: Int? = null,
    val hasRecoveryCode: Boolean? = null, val consentVersion: String? = null,
)
@Serializable data class School(val id: String, val name: String, val englishName: String,
    val region: String, val address: String, val kind: String) {
    val displayName get() = englishName.ifBlank { name }
}
@Serializable data class SchoolsResult(val schools: List<School>)
@Serializable data class Session(val token: String, val recoveryCode: String? = null)
@Serializable data class RecoveryResult(val recoveryCode: String)
@Serializable data class PeopleResult(val people: List<User> = emptyList())
@Serializable data class FriendsResult(val friends: List<User> = emptyList(),
    val requests: List<User> = emptyList(), val sent: List<User> = emptyList())
@Serializable data class PollOption(val id: String, val userId: String, val userName: String)
@Serializable data class Poll(val id: String, val question: String, val emoji: String,
    val backgroundColor: String, val options: List<PollOption>)
@Serializable data class PollsResult(val polls: List<Poll> = emptyList(), val answered: Int = 0,
    val total: Int = 12, val day: String = "", val skipped: Int = 0,
    val minimumFriends: Int = 4, val friendCount: Int = 0)
@Serializable data class VoteResult(val coinsEarned: Int)
@Serializable data class Flame(val id: String, val pollQuestion: String, val day: String, val isRead: Boolean)
@Serializable data class InboxResult(val flames: List<Flame> = emptyList(), val unreadCount: Int = 0,
    val nextCursor: String? = null)
@Serializable data class DeviceSession(val id: String, val device: String, val created: Double,
    val expires: Double, val current: Boolean)
@Serializable data class SessionsResult(val sessions: List<DeviceSession>)
@Serializable data class CoinEntry(val id: String, val amount: Int, val reason: String, val timestamp: String)
@Serializable data class LedgerResult(val entries: List<CoinEntry>)
@Serializable data class Report(val id: String, val reason: String, val timestamp: String,
    val status: String, val resolution: String)
@Serializable data class ReportsResult(val reports: List<Report>)
@Serializable data class Invitation(val code: String, val expires: Double)
@Serializable data class OfflineSnapshot(val user: User, val friends: FriendsResult,
    val inbox: InboxResult, val savedAt: Long = System.currentTimeMillis())
