package app.gas.korea.data

import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.Call
import okhttp3.Callback
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

class ApiException(val status: Int, message: String) : Exception(message)

// Immutable connection: requests can never accidentally use another server's token.
class ApiClient(val server: String, val token: String?, private val debug: Boolean) {
    suspend fun raw(path: String, method: String = "GET", body: JsonObject? = null,
                    query: Map<String, String> = emptyMap()): String {
        require(path.startsWith("/v1/") || path == "/health")
        val url = (ServerAddress.normalize(server, debug) + path).toHttpUrl().newBuilder().apply {
            query.forEach { (key, value) -> addQueryParameter(key, value) }
        }.build()
        val request = Request.Builder().url(url).header("Accept", "application/json").apply {
            token?.let { header("Authorization", "Bearer $it") }
            method(method, if (method == "GET") null else (body?.toString() ?: "{}").toRequestBody(JSON))
        }.build()
        return suspendCancellableCoroutine { continuation ->
            val call = http.newCall(request)
            continuation.invokeOnCancellation { call.cancel() }
            call.enqueue(object : Callback {
                override fun onFailure(call: Call, e: IOException) { if (!continuation.isCancelled) continuation.resumeWithException(e) }
                override fun onResponse(call: Call, response: Response) {
                    try {
                        response.use {
                            val text = it.body?.string() ?: throw IOException("Empty server response.")
                            if (!it.isSuccessful) {
                                val message = runCatching { WireJson.parseToJsonElement(text).jsonObject["error"]?.jsonPrimitive?.content }.getOrNull()
                                throw ApiException(it.code, message ?: "Server returned HTTP ${it.code}.")
                            }
                            continuation.resume(text)
                        }
                    } catch (e: Exception) { if (!continuation.isCancelled) continuation.resumeWithException(e) }
                }
            })
        }
    }

    suspend inline fun <reified T> get(path: String, query: Map<String, String> = emptyMap()): T =
        WireJson.decodeFromString(raw(path, query = query))

    suspend inline fun <reified T> post(path: String, body: JsonObject): T =
        WireJson.decodeFromString(raw(path, "POST", body))

    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()
        // Refuse redirects: no credential forwarding or HTTPS-to-HTTP downgrade.
        private val http = OkHttpClient.Builder().followRedirects(false).followSslRedirects(false)
            .connectTimeout(20, TimeUnit.SECONDS).callTimeout(25, TimeUnit.SECONDS).build()
    }
}
