package app.gas.korea

import android.content.Context
import android.graphics.Bitmap
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import app.gas.korea.data.*
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.io.File

/** Uses a local fixture server only; never connects to a user's real account. */
class ScreenSmokeTest {
    @get:Rule val compose = createEmptyComposeRule()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    @Test fun tabsRenderAndKeystoreCacheIsIsolated() {
        val server = MockWebServer()
        val user = User("alex", "alex", "Alex Kim", "Seoul Demo School", "demo", coins = 120,
            hasRecoveryCode = true, consentVersion = CONSENT_VERSION)
        val friends = listOf("Jamie", "Min", "Taylor", "Sam").mapIndexed { index, name -> User("friend$index", name.lowercase(), name, user.school, "demo") }
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val response = when (request.requestUrl?.encodedPath) {
                    "/v1/me" -> WireJson.encodeToString(user)
                    "/v1/friends" -> WireJson.encodeToString(FriendsResult(friends = friends))
                    "/v1/inbox" -> WireJson.encodeToString(InboxResult(listOf(Flame("flame", "Makes everyone feel included", "2026-10-08", false)), 1))
                    "/v1/blocks" -> "{\"people\":[]}"
                    "/v1/polls" -> WireJson.encodeToString(PollsResult(polls = listOf(Poll("poll", "Who always makes you laugh?", "😂", "orange",
                        friends.map { PollOption(it.id, it.id, it.name) })), day = "2026-10-08", friendCount = 4))
                    else -> "{\"ok\":true}"
                }
                return MockResponse().setBody(response).setHeader("Content-Type", "application/json")
            }
        }
        server.start()
        val origin = server.url("/").toString().trimEnd('/')
        val preferences = context.getSharedPreferences("gas.settings", Context.MODE_PRIVATE)
        val previousServer = preferences.getString("server", null)
        val vault = SecureStore(context)
        val testToken = "instrumentation-test-token"
        try {
            vault.saveToken(origin, testToken)
            assertEquals(testToken, vault.token(origin))
            assertNull(vault.token("https://other.example"))
            vault.saveCache(origin, testToken, OfflineSnapshot(user, FriendsResult(friends), InboxResult()))
            assertEquals(user.id, vault.cache(origin, testToken)?.user?.id)
            assertNull(vault.cache(origin, "different-session"))
            vault.saveCache(origin, "expired", OfflineSnapshot(user, FriendsResult(), InboxResult(), savedAt = 1L))
            assertNull(vault.cache(origin, "expired"))
            preferences.edit().putString("server", origin).commit()
            ActivityScenario.launch(MainActivity::class.java).use {
                compose.waitUntil(60_000) { compose.onAllNodesWithText("Who always makes you laugh?").fetchSemanticsNodes().isNotEmpty() }
                compose.onNodeWithText("Jamie").assertIsDisplayed()
                screenshot("polls")
                compose.onNodeWithText("Inbox").performClick()
                compose.onNodeWithText("Makes everyone feel included").assertIsDisplayed()
                screenshot("inbox")
                compose.onNodeWithText("Friends").performClick()
                compose.onNodeWithText("Friends · 4").assertIsDisplayed()
                screenshot("friends")
                compose.onNodeWithText("Profile").performClick()
                compose.onNodeWithText("Alex Kim").assertIsDisplayed()
                screenshot("profile")
            }
            vault.clearCache(origin, testToken)
            assertNull(vault.cache(origin, testToken))
        } finally {
            vault.saveToken(origin, null); vault.clearCache(origin, testToken)
            preferences.edit().putString("server", previousServer).commit()
            server.shutdown()
        }
    }

    private fun screenshot(name: String) {
        compose.waitForIdle()
        val bitmap = compose.onRoot().captureToImage().asAndroidBitmap()
        val directory = File(context.getExternalFilesDir(null), "screenshots").apply { mkdirs() }
        File(directory, "$name.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }
}
