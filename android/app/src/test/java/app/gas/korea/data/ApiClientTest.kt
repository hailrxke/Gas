package app.gas.korea.data

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class ApiClientTest {
    private val server = MockWebServer()
    private lateinit var api: ApiClient
    @Before fun setup() { server.start(); api = ApiClient(server.url("/").toString().trimEnd('/'), "session-secret", true) }
    @After fun cleanup() { server.shutdown() }

    @Test fun encodesSearchAndSendsBearer() = runBlocking {
        server.enqueue(MockResponse().setBody("{\"people\":[]}"))
        api.get<PeopleResult>("/v1/people", mapOf("q" to "A+B & 한글"))
        val request = server.takeRequest()
        assertEquals("A+B & 한글", request.requestUrl!!.queryParameter("q"))
        assertEquals("Bearer session-secret", request.getHeader("Authorization"))
    }
    @Test fun patchPreservesPasswordWhitespaceAndBooleanTypes() = runBlocking {
        server.enqueue(MockResponse().setBody("{\"ok\":true}"))
        val payload = body("password" to "  ten characters  ", "confirmSchoolChange" to true)
        api.raw("/v1/me", "PATCH", payload)
        val request = server.takeRequest()
        assertEquals("PATCH", request.method)
        assertEquals(payload, WireJson.parseToJsonElement(request.body.readUtf8()))
    }
    @Test fun surfacesApiErrorsAndDoesNotFollowRedirects() = runBlocking {
        for (status in listOf(401, 409, 428, 429)) {
            server.enqueue(MockResponse().setResponseCode(status).setBody("{\"error\":\"Specific error\"}"))
            try { api.raw("/v1/me"); fail("Expected failure") }
            catch (e: ApiException) { assertEquals(status, e.status); assertEquals("Specific error", e.message) }
        }
        server.enqueue(MockResponse().setResponseCode(302).setHeader("Location", server.url("/v1/redirect")))
        try { api.raw("/v1/me"); fail("Redirect must fail") }
        catch (e: ApiException) { assertEquals(302, e.status) }
        assertEquals(5, server.requestCount)
    }
    @Test fun decodesNullableCursorAndPrivateLegacyFields() {
        val inbox = WireJson.decodeFromString<InboxResult>("""{"flames":[{"id":"f","pollQuestion":"Kindest","day":"2026-10-07","isRead":false}],"unreadCount":73,"nextCursor":null}""")
        assertEquals(73, inbox.unreadCount); assertNull(inbox.nextCursor)
        val user = WireJson.decodeFromString<User>("""{"id":"u","name":"Alex","username":"alex","school":"Demo","schoolId":"s","age":null,"birthDate":null,"futureField":true}""")
        assertNull(user.birthDate)
    }
}
