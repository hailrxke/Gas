package app.gas.korea.ui

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import app.gas.korea.GasViewModel
import app.gas.korea.data.*
import app.gas.korea.notifications.DailyReminder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.LocalDate

@Composable fun ProfileScreen(vm: GasViewModel, navigate: (String) -> Unit) {
    val context = LocalContext.current
    var reminder by remember { mutableStateOf(DailyReminder.enabled(context)) }
    fun enableReminder() {
        try { DailyReminder.enable(context); reminder = true }
        catch (e: Exception) { reminder = false; vm.error = e.message }
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { allowed ->
        if (allowed) enableReminder() else { reminder = false; vm.error = "Notifications are disabled. You can allow them in Android Settings." }
    }
    Form {
        vm.user?.let { user ->
            Group {
                Icon(Icons.Default.AccountCircle, null, Modifier.size(64.dp), tint = Orange)
                Text(user.name, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                Hint("@${user.username}")
                Hint(user.school)
                Link("Edit Profile") { navigate("Edit Profile") }
            }
            Group("Activity") {
                Text("★ ${user.coins ?: 0} coins", style = MaterialTheme.typography.titleLarge)
                Hint("Friends: ${vm.friends.friends.size}")
                Link("Coin History") { navigate("Coin History") }
            }
            if (user.hasRecoveryCode != true) Hint("Protect your account: create a recovery code in Password & Recovery.")
        }
        Group("Account") {
            listOf("Password & Recovery", "Active Sessions", "My Reports", "Export or Delete My Data").forEach { label ->
                Link(label) { navigate(label) }
            }
        }
        Group {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Daily poll reminder", Modifier.weight(1f))
                Switch(reminder, { enabled ->
                    if (!enabled) { DailyReminder.disable(context); reminder = false }
                    else if (Build.VERSION.SDK_INT >= 33 && !DailyReminder.permitted(context)) permission.launch(Manifest.permission.POST_NOTIFICATIONS)
                    else enableReminder()
                })
            }
            Hint("Around 8 PM in your device's time zone. Android battery saving may delay it. This is not a notification about incoming compliments.")
        }
        Group {
            Link("Privacy Information") { navigate("Privacy Information") }
            Link("Log Out", !vm.busy) { vm.logout() }
        }
    }
}

@Composable fun EditProfileScreen(vm: GasViewModel, done: () -> Unit) {
    val user = vm.user ?: return
    var name by rememberSaveable { mutableStateOf(user.name) }
    var username by rememberSaveable { mutableStateOf(user.username) }
    var school by remember { mutableStateOf<School?>(null) }
    var password by remember { mutableStateOf("") }
    var confirm by remember { mutableStateOf(false) }
    val changingSchool = school != null && school?.id != user.schoolId
    fun save() = vm.mutate("/v1/me", body("name" to name, "username" to username,
        "schoolId" to (school?.id ?: user.schoolId), "confirmSchoolChange" to changingSchool, "password" to password), "PATCH") {
        password = ""; done()
    }
    Form {
        Group {
            Field("Name or nickname", name, { name = it })
            Field("Username", username, { username = it })
            SchoolField(vm, school, user.school) { school = it }
            if (changingSchool) {
                Hint("Changing schools removes all friendships, pending requests and your invitation code. Your vote history and points remain.")
                Field("Current password", password, { password = it }, secret = true)
            }
        }
        Primary("Save Changes", !vm.busy && !vm.offline && name.trim().isNotEmpty() && name.codePointCount(0, name.length) <= 40 && validUsername(username) &&
            (!changingSchool || validPassword(password))) { if (changingSchool) confirm = true else save() }
    }
    if (confirm) Confirm("Change School?", "Remove your friendships, pending requests and invitation code?", "Change School", { confirm = false }, ::save)
}

@Composable fun PasswordScreen(vm: GasViewModel) {
    var current by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var confirmation by remember { mutableStateOf("") }
    Form {
        Group { Field("Current password", current, { current = it }, secret = true) }
        Group("Change password") {
            Field("New password", password, { password = it }, secret = true)
            Field("Confirm password", confirmation, { confirmation = it }, secret = true)
            Hint("This signs out every other session and replaces your recovery code.")
            Primary("Change Password", !vm.busy && !vm.offline && validPassword(current) && validPassword(password) && password == confirmation) {
                vm.replaceSession("/v1/password", body("password" to current, "newPassword" to password)) {
                    current = ""; password = ""; confirmation = ""; vm.notice = "Password changed. Other sessions were signed out."
                }
            }
        }
        Group("Recovery code") {
            Hint("Create a replacement using your current password. The previous code stops working immediately.")
            Link("Replace Recovery Code", !vm.busy && !vm.offline && validPassword(current)) { vm.replaceRecovery(current) { current = "" } }
        }
    }
}

@Composable fun SessionsScreen(vm: GasViewModel) {
    var sessions by remember { mutableStateOf<List<DeviceSession>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var refresh by remember { mutableIntStateOf(0) }
    LaunchedEffect(refresh) { loading = true; vm.read { it.get<SessionsResult>("/v1/sessions") }?.let { sessions = it.sessions }; loading = false }
    Form {
        if (loading) LinearProgressIndicator(Modifier.fillMaxWidth())
        Link("Refresh", !loading) { refresh++ }
        sessions.forEach { session -> Group {
            Text(session.device + if (session.current) " · This session" else "", fontWeight = FontWeight.Bold)
            Hint("Signed in: ${formatTime(session.created)}")
            Hint("Expires: ${formatTime(session.expires)}")
            if (!session.current) Link("Sign Out Session", !vm.busy && !vm.offline, danger = true) {
                vm.mutate("/v1/sessions", body("id" to session.id), "DELETE") { refresh++ }
            }
        } }
        Link("Sign Out All Other Sessions", !vm.busy && !vm.offline && sessions.any { !it.current }, danger = true) {
            vm.mutate("/v1/sessions", body("allOthers" to true), "DELETE") { refresh++ }
        }
    }
}

@Composable fun LedgerScreen(vm: GasViewModel) {
    var entries by remember { mutableStateOf<List<CoinEntry>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var refresh by remember { mutableIntStateOf(0) }
    LaunchedEffect(refresh) { loading = true; vm.read { it.get<LedgerResult>("/v1/ledger") }?.let { entries = it.entries }; loading = false }
    Form {
        Hint("Latest 100 entries. Export your data for the full history. Coins have no cash value.")
        if (loading) LinearProgressIndicator(Modifier.fillMaxWidth())
        Link("Refresh", !loading) { refresh++ }
        if (!loading && entries.isEmpty()) Hint("No coin history yet.")
        entries.forEach { entry -> Group {
            Text("${if (entry.amount > 0) "+" else ""}${entry.amount} · ${entry.reason}", style = MaterialTheme.typography.titleMedium)
            Hint(entry.timestamp)
        } }
    }
}

@Composable fun ReportsScreen(vm: GasViewModel) {
    var reports by remember { mutableStateOf<List<Report>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var refresh by remember { mutableIntStateOf(0) }
    var unblock by remember { mutableStateOf<Report?>(null) }
    var reset by remember { mutableStateOf(false) }
    LaunchedEffect(refresh) { loading = true; vm.read { it.get<ReportsResult>("/v1/reports") }?.let { reports = it.reports }; loading = false }
    Form {
        Hint("Latest 100 reports. Older reports may expire. You can still reset all anonymous sender blocks.")
        Link("Reset All Anonymous Sender Blocks", !vm.busy && !vm.offline, danger = true) { reset = true }
        if (loading) LinearProgressIndicator(Modifier.fillMaxWidth())
        Link("Refresh", !loading) { refresh++ }
        if (!loading && reports.isEmpty()) Hint("No reports yet.")
        reports.forEach { report -> Group {
            Text(report.reason, style = MaterialTheme.typography.titleMedium)
            Hint(report.status.replace('_', ' '))
            Hint(report.timestamp)
            if (report.resolution.isNotBlank()) Text(report.resolution)
            Link("Undo Sender Block", !vm.busy && !vm.offline) { unblock = report }
        } }
    }
    if (reset) Confirm("Reset blocks?", "Allow compliments from all anonymously blocked senders again?", "Reset Blocks", { reset = false }) {
        vm.mutate("/v1/blocks/anonymous", method = "DELETE")
    }
    unblock?.let { report -> Confirm("Unblock sender?", "Their compliments will appear again. Their identity stays hidden.", "Unblock", { unblock = null }) {
        vm.mutate("/v1/reports/unblock", body("id" to report.id))
    } }
}

@Composable fun AccountDataScreen(vm: GasViewModel) {
    var password by remember { mutableStateOf("") }
    var deleting by remember { mutableStateOf(false) }
    var export by remember { mutableStateOf<String?>(null) }
    var saving by remember { mutableStateOf(false) }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val save = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri ->
        val json = export; export = null
        if (uri != null && json != null) scope.launch {
            saving = true
            try {
                withContext(Dispatchers.IO) {
                    val stream = context.contentResolver.openOutputStream(uri) ?: error("Could not open this destination.")
                    stream.use { it.write(json.toByteArray()) }
                }
                vm.notice = "Your data was exported. Keep this file private."
            } catch (e: Exception) { vm.error = "Could not save the export: ${e.message}" }
            finally { saving = false }
        }
    }
    Form {
        Group { Field("Current password", password, { password = it }, secret = true) }
        Group("Export") {
            Hint("Save your profile, friendships, votes, coin history and reports as JSON. Anonymous sender identities are never included. Keep the file private.")
            Primary(if (saving) "Saving…" else "Export My Data", !vm.busy && !vm.offline && !saving && export == null && validPassword(password)) {
                vm.export(password) { export = it; password = ""; save.launch("gas-export-${LocalDate.now()}.json") }
            }
        }
        Group("Delete account") {
            Hint("This permanently removes your profile, sessions, friendships and coin balance. Delivered compliments stay anonymous, with your account link removed. This cannot be undone.")
            Link("Delete Account", !vm.busy && !vm.offline && !saving && validPassword(password), danger = true) { deleting = true }
        }
    }
    if (deleting) Confirm("Permanently delete your account?", "Your profile, friendships and balance will be removed. This cannot be undone.", "Delete Permanently", { deleting = false }) {
        vm.logout(deletePassword = password); password = ""
    }
}
