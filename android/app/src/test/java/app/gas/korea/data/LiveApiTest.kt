package app.gas.korea.data

import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.net.ServerSocket
import java.nio.file.Files
import java.time.LocalDate
import java.util.concurrent.TimeUnit

/** Runs the actual Android HTTP client against this repository's Python API in an isolated DB. */
class LiveApiTest {
    @Test fun completeAccountAndComplimentLifecycle() = runBlocking {
        val root = File(requireNotNull(System.getProperty("gas.repo")))
        val python = System.getenv("GAS_TEST_PYTHON") ?: if (System.getProperty("os.name").orEmpty().startsWith("Windows")) "python" else "python3"
        val temporary = Files.createTempDirectory("gas-android-test-").toFile()
        val database = File(temporary, "gas.sqlite3")
        val log = File(temporary, "server.log")
        val port = ServerSocket(0).use { it.localPort }
        var process: Process? = null
        try {
            val importer = ProcessBuilder(python, "-X", "utf8", File(root, "server/manage.py").path, "--database", database.path,
                "import-schools", File(root, "server/examples/schools.json").path)
                .redirectErrorStream(true).redirectOutput(log).start()
            assertTrue("Catalog import timed out", importer.waitFor(20, TimeUnit.SECONDS))
            assertEquals(log.readText(), 0, importer.exitValue())
            process = ProcessBuilder(python, "-X", "utf8", File(root, "server/app.py").path).apply {
                environment()["GAS_DATABASE"] = database.path
                environment()["GAS_HOST"] = "127.0.0.1"
                environment()["PORT"] = port.toString()
                redirectErrorStream(true); redirectOutput(ProcessBuilder.Redirect.appendTo(log))
            }.start()
            val server = "http://127.0.0.1:$port"
            val public = ApiClient(server, null, true)
            var healthy = false
            for (attempt in 0 until 50) {
                if (runCatching { public.raw("/health") }.isSuccess) { healthy = true; break }
                delay(100)
            }
            assertTrue(log.readText(), healthy)
            val schools = public.get<SchoolsResult>("/v1/schools").schools
            val password = "Android test password"
            val sessions = (0..4).map { index ->
                public.post<Session>("/v1/register", body("username" to "android_$index", "password" to password,
                    "name" to "Android $index", "schoolId" to schools.first().id,
                    "birthDate" to LocalDate.now().minusYears(16).withDayOfMonth(1).toString(),
                    "consent" to true, "consentVersion" to CONSENT_VERSION, "deviceName" to "Android integration test"))
            }
            assertNotNull(sessions.first().recoveryCode)
            val clients = sessions.map { ApiClient(server, it.token, true) }
            val users = clients.map { it.get<User>("/v1/me") }
            val main = clients.first()
            val invite = main.post<Invitation>("/v1/invites", body())
            clients[1].raw("/v1/invites/accept", "POST", body("code" to invite.code))
            main.raw("/v1/friends", "POST", body("userId" to users[1].id))
            for (index in 2..4) {
                main.raw("/v1/friends", "POST", body("userId" to users[index].id))
                clients[index].raw("/v1/friends", "POST", body("userId" to users.first().id))
            }
            assertEquals(4, main.get<FriendsResult>("/v1/friends").friends.size)
            assertTrue(main.get<PeopleResult>("/v1/people", mapOf("q" to "Android")).people.isNotEmpty())
            var polls = main.get<PollsResult>("/v1/polls")
            assertEquals(12, polls.polls.size)
            main.raw("/v1/polls/skip", "POST", body("pollId" to polls.polls.first().id, "day" to polls.day))
            assertEquals(1, main.get<PollsResult>("/v1/polls").skipped)
            main.raw("/v1/polls/restore", "POST", body("day" to polls.day))
            polls = main.get("/v1/polls")
            val poll = polls.polls.first()
            val recipientId = poll.options.first().userId
            val vote = body("pollId" to poll.id, "selectedUserId" to recipientId, "day" to polls.day)
            assertEquals(20, main.post<VoteResult>("/v1/votes", vote).coinsEarned)
            runCatching { main.post<VoteResult>("/v1/votes", vote) }
            assertEquals(20, main.get<User>("/v1/me").coins)
            assertEquals(1, main.get<LedgerResult>("/v1/ledger").entries.size)
            val recipient = clients[users.indexOfFirst { it.id == recipientId }]
            val inbox = recipient.get<InboxResult>("/v1/inbox")
            assertEquals(1, inbox.unreadCount)
            assertEquals(poll.question, inbox.flames.single().pollQuestion)
            val rawInbox = recipient.raw("/v1/inbox")
            assertFalse(rawInbox.contains("senderId")); assertFalse(rawInbox.contains(users.first().id))
            val flame = inbox.flames.single()
            recipient.raw("/v1/inbox/read", "POST", body("id" to flame.id))
            assertEquals(0, recipient.get<InboxResult>("/v1/inbox").unreadCount)
            recipient.raw("/v1/reports", "POST", body("id" to flame.id, "reason" to "Test report"))
            assertTrue(recipient.get<InboxResult>("/v1/inbox").flames.isEmpty())
            val report = recipient.get<ReportsResult>("/v1/reports").reports.single()
            recipient.raw("/v1/reports/unblock", "POST", body("id" to report.id))
            assertEquals(1, recipient.get<InboxResult>("/v1/inbox").flames.size)
            main.raw("/v1/me", "PATCH", body("name" to "Updated", "username" to "android_0", "schoolId" to schools.first().id))
            assertEquals("Updated", main.get<User>("/v1/me").name)
            val export = WireJson.parseToJsonElement(main.raw("/v1/export", "POST", body("password" to password))).jsonObject
            assertTrue(export.isNotEmpty())
            val other = public.post<Session>("/v1/login", body("username" to "android_0", "password" to password))
            assertEquals(2, main.get<SessionsResult>("/v1/sessions").sessions.size)
            main.raw("/v1/sessions", "DELETE", body("allOthers" to true))
            expectStatus(401) { ApiClient(server, other.token, true).raw("/v1/me") }
            val changed = main.post<Session>("/v1/password", body("password" to password, "newPassword" to "replacement password"))
            expectStatus(401) { main.raw("/v1/me") }
            val recovered = public.post<Session>("/v1/recover", body("username" to "android_0",
                "recoveryCode" to changed.recoveryCode!!, "newPassword" to "recovered password"))
            expectStatus(401) { ApiClient(server, changed.token, true).raw("/v1/me") }
            val recoveredClient = ApiClient(server, recovered.token, true)
            assertNotNull(recoveredClient.post<RecoveryResult>("/v1/recovery-code", body("password" to "recovered password")).recoveryCode)
            recoveredClient.raw("/v1/me", "DELETE", body("password" to "recovered password"))
            expectStatus(401) { recoveredClient.raw("/v1/me") }
        } finally {
            process?.destroy()
            process?.waitFor(5, TimeUnit.SECONDS)
            if (process?.isAlive == true) process.destroyForcibly().waitFor()
            // Only this test's freshly created temporary directory is removed.
            temporary.deleteRecursively()
        }
    }

    private suspend fun expectStatus(status: Int, action: suspend () -> Unit) {
        try { action(); fail("Expected HTTP $status") }
        catch (e: ApiException) { assertEquals(status, e.status) }
    }
}
