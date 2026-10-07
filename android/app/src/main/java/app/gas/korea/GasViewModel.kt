package app.gas.korea

import android.app.Application
import android.os.Build
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import app.gas.korea.data.*
import app.gas.korea.notifications.DailyReminder
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.json.JsonObject
import java.io.IOException

class GasViewModel(application: Application) : AndroidViewModel(application) {
    private val preferences = application.getSharedPreferences("gas.settings", 0)
    private val vault = SecureStore(application)
    private val gate = Mutex()
    private var token: String? = null
    private var inboxJob: Job? = null
    var server by mutableStateOf(preferences.getString("server", null) ?: if (BuildConfig.DEBUG) "http://10.0.2.2:8080" else "")
        private set
    var user by mutableStateOf<User?>(null); private set
    var friends by mutableStateOf(FriendsResult()); private set
    var inbox by mutableStateOf(InboxResult()); private set
    var blocked by mutableStateOf<List<User>>(emptyList()); private set
    var polls by mutableStateOf(PollsResult()); private set
    var pollReady by mutableStateOf(false); private set
    var inboxQuery by mutableStateOf(""); private set
    var busy by mutableStateOf(false); private set
    var restoring by mutableStateOf(true); private set
    var offline by mutableStateOf(false); private set
    var needsConsent by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null)
    var notice by mutableStateOf<String?>(null)
    var recoveryCode by mutableStateOf<String?>(null); private set
    val hasSession get() = token != null
    private val api get() = ApiClient(server, token, BuildConfig.DEBUG)

    init { retrySession() }

    // All session mutations and authenticated reads share a gate. No late response can
    // overwrite a newer login/logout; search cancellation also cancels its HTTP call.
    private fun action(block: suspend () -> Unit) {
        if (busy) return
        busy = true
        viewModelScope.launch {
            try { gate.withLock { block() } }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) { handle(e) }
            finally { busy = false }
        }
    }

    private fun handle(e: Exception) {
        when {
            e is ApiException && e.status == 401 && token != null -> { clearSession(); error = "Your session ended. Please log in again." }
            e is ApiException && e.status == 428 -> { needsConsent = true }
            else -> {
                if (e is IOException) offline = true
                error = if (e is IOException) "Could not reach the server. Check your connection and Server Settings, then retry." else e.message ?: "Something went wrong. Please try again."
            }
        }
    }

    fun retrySession() = action {
        restoring = true
        try {
            if (server.isBlank()) return@action
            if (token == null) token = try { vault.token(server) } catch (_: Exception) {
                vault.saveToken(server, null)
                error = "The saved session could not be unlocked. Please log in again."; null
            }
            val sessionToken = token ?: return@action
            vault.cache(server, sessionToken)?.let {
                user = it.user; friends = it.friends; inbox = it.inbox; offline = true
                needsConsent = it.user.consentVersion != CONSENT_VERSION
            }
            refreshLocked()
        } finally { restoring = false }
    }

    fun configure(address: String, done: () -> Unit) = action {
        check(token == null) { "Log out before changing servers." }
        server = ServerAddress.normalize(address, BuildConfig.DEBUG)
        preferences.edit().putString("server", server).apply()
        resetMemory()
        token = vault.token(server)
        done()
        if (token != null) refreshLocked()
    }

    fun authenticate(register: Boolean, username: String, password: String, name: String = "",
                     schoolId: String = "", birthDate: String = "") = action {
        val fields = body("username" to username, "password" to password, "deviceName" to "Android ${Build.MODEL}")
        val payload = if (register) JsonObject(fields + body("name" to name, "schoolId" to schoolId,
            "birthDate" to birthDate, "consent" to true, "consentVersion" to CONSENT_VERSION)) else fields
        install(api.post(if (register) "/v1/register" else "/v1/login", payload))
    }

    fun replaceSession(path: String, payload: JsonObject, done: () -> Unit = {}) = action {
        install(api.post(path, JsonObject(payload + body("deviceName" to "Android ${Build.MODEL}"))))
        done()
    }

    private suspend fun install(session: Session) {
        val old = token
        try { vault.saveToken(server, session.token) }
        catch (e: Exception) {
            runCatching { ApiClient(server, session.token, BuildConfig.DEBUG).raw("/v1/logout", "POST") }
            throw IOException("Could not securely save your session.", e)
        }
        old?.let { vault.clearCache(server, it) }
        resetMemory(); token = session.token
        // Show this even if the subsequent profile request loses connectivity.
        recoveryCode = session.recoveryCode
        refreshLocked()
    }

    fun dismissRecovery() { recoveryCode = null }

    suspend fun refresh(automatic: Boolean = false) {
        if (!gate.tryLock()) return
        try {
            if (token != null) refreshLocked(automatic)
        } catch (e: CancellationException) { throw e }
        catch (e: Exception) { handle(e) }
        finally { gate.unlock() }
    }

    fun refreshNow() = action { refreshLocked() }

    private suspend fun refreshLocked(preserveInbox: Boolean = false) {
        if (token == null) return
        user = api.get("/v1/me")
        offline = false
        needsConsent = user?.consentVersion != CONSENT_VERSION
        if (needsConsent) return
        friends = api.get("/v1/friends")
        val firstPage: InboxResult = api.get("/v1/inbox", mapOf("q" to inboxQuery))
        inbox = if (preserveInbox && inbox.flames.size > 50) inbox.copy(unreadCount = firstPage.unreadCount) else firstPage
        blocked = api.get<PeopleResult>("/v1/blocks").people
        loadPollsLocked()
        api.raw("/v1/activity", "POST")
        saveCache()
    }

    private fun saveCache() {
        val currentUser = user ?: return
        val currentToken = token ?: return
        if (inboxQuery.isNotBlank()) return
        try { vault.saveCache(server, currentToken, OfflineSnapshot(currentUser, friends,
            inbox.copy(flames = inbox.flames.take(50), nextCursor = null))) }
        catch (_: Exception) { notice = "Offline storage is unavailable. Your online data is unaffected." }
    }

    fun searchInbox(query: String) {
        inboxQuery = query
        inboxJob?.cancel()
        inboxJob = viewModelScope.launch {
            kotlinx.coroutines.delay(300)
            try {
                gate.withLock {
                    if (token == null) return@withLock
                    inbox = api.get("/v1/inbox", mapOf("q" to query)); offline = false; saveCache()
                }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { handle(e) }
        }
    }

    fun loadOlder() = action {
        val cursor = inbox.nextCursor ?: return@action
        try {
            val page: InboxResult = api.get("/v1/inbox", mapOf("q" to inboxQuery, "cursor" to cursor))
            inbox = page.copy(flames = (inbox.flames + page.flames).distinctBy { it.id })
        } catch (e: ApiException) {
            if (e.status == 400) { inbox = api.get("/v1/inbox", mapOf("q" to inboxQuery)); notice = "Inbox changed. Showing the newest compliments." }
            else throw e
        }
    }

    suspend fun schools(query: String): List<School> = ApiClient(server, null, BuildConfig.DEBUG)
        .get<SchoolsResult>("/v1/schools", mapOf("q" to query)).schools

    suspend fun people(query: String): List<User> = gate.withLock {
        try { api.get<PeopleResult>("/v1/people", mapOf("q" to query)).people }
        catch (e: ApiException) { handle(e); throw e }
    }

    fun mutate(path: String, payload: JsonObject = body(), method: String = "POST", done: () -> Unit = {}) = action {
        api.raw(path, method, payload)
        done()
        refreshLocked()
    }

    fun <T> fetch(loader: suspend (ApiClient) -> T, result: (T) -> Unit) = action {
        result(loader(api))
    }

    suspend fun <T> read(loader: suspend (ApiClient) -> T): T? = gate.withLock {
        try { loader(api) }
        catch (e: CancellationException) { throw e }
        catch (e: Exception) { handle(e); null }
    }

    fun replaceRecovery(password: String, done: () -> Unit) = action {
        recoveryCode = api.post<RecoveryResult>("/v1/recovery-code", body("password" to password)).recoveryCode
        done()
    }

    private suspend fun loadPollsLocked() {
        pollReady = false
        polls = api.get("/v1/polls"); pollReady = true
    }

    fun vote(option: PollOption) = pollAction { poll ->
        val result = api.post<VoteResult>("/v1/votes", body("pollId" to poll.id, "selectedUserId" to option.userId, "day" to polls.day))
        notice = "+${result.coinsEarned} coins · You made someone's day!"
    }

    private fun pollAction(operation: suspend (Poll) -> Unit) = action {
        val poll = polls.polls.firstOrNull() ?: return@action
        try { operation(poll) }
        catch (e: CancellationException) { throw e }
        catch (e: Exception) { handle(e) }
        finally {
            // Lost responses may have committed. Disable stale options until refreshed.
            pollReady = false
        }
        if (token != null) refreshLocked()
    }

    fun changePoll(action: String) {
        if (action == "restore") {
            mutate("/v1/polls/restore", body("day" to polls.day))
        } else pollAction { poll -> api.raw("/v1/polls/$action", "POST", body("pollId" to poll.id, "day" to polls.day)) }
    }

    fun logout(deletePassword: String? = null) = action {
        try {
            api.raw(if (deletePassword == null) "/v1/logout" else "/v1/me",
                if (deletePassword == null) "POST" else "DELETE",
                if (deletePassword == null) body() else body("password" to deletePassword))
        } catch (e: IOException) {
            if (deletePassword != null) throw e
            notice = "Signed out on this device. Revoke the unreachable server session later from Active Sessions."
        }
        clearSession()
    }

    fun export(password: String, ready: (String) -> Unit) = action {
        ready(api.raw("/v1/export", "POST", body("password" to password)))
    }

    private fun clearSession() {
        vault.saveToken(server, null)
        token?.let { vault.clearCache(server, it) }
        token = null; resetMemory()
        DailyReminder.disable(getApplication())
    }

    private fun resetMemory() {
        inboxJob?.cancel()
        user = null; friends = FriendsResult(); inbox = InboxResult(); blocked = emptyList()
        polls = PollsResult(); pollReady = false; inboxQuery = ""; recoveryCode = null
        needsConsent = false; offline = false
    }
}
