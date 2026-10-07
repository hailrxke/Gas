@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
package app.gas.korea.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import app.gas.korea.GasViewModel
import app.gas.korea.data.*
import kotlinx.coroutines.delay

@Composable fun GasApp(vm: GasViewModel) {
    var page by rememberSaveable { mutableStateOf("") }
    var tab by rememberSaveable { mutableIntStateOf(0) }
    var navigationUser by rememberSaveable { mutableStateOf(vm.user?.id) }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(vm.user?.id, vm.restoring) {
        if (!vm.restoring && navigationUser != vm.user?.id) {
            navigationUser = vm.user?.id; page = ""; tab = 0
        }
    }
    LaunchedEffect(lifecycle, vm.user?.id) {
        if (vm.user != null) lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
            while (true) { delay(30_000); vm.refresh(automatic = true) }
        }
    }
    LaunchedEffect(vm.notice) { vm.notice?.let { snackbar.showSnackbar(it); vm.notice = null } }
    BackHandler(page.isNotEmpty()) { page = "" }
    val signedIn = vm.user != null
    val tabs = listOf("Polls", "Inbox", "Friends", "Profile")
    val icons = listOf(Icons.Default.LocalFireDepartment, Icons.Default.Inbox, Icons.Default.People, Icons.Default.AccountCircle)
    Scaffold(
        snackbarHost = { SnackbarHost(snackbar) },
        topBar = {
            if (!vm.restoring) TopAppBar(
                title = { Text(page.ifEmpty { if (signedIn) if (vm.needsConsent) "Privacy information" else tabs[tab] else "Welcome" }) },
                navigationIcon = { if (page.isNotEmpty()) IconButton(onClick = { page = "" }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
                actions = { if (signedIn && page.isEmpty() && !vm.needsConsent) IconButton(onClick = vm::refreshNow, enabled = !vm.busy) { Icon(Icons.Default.Refresh, "Refresh") } })
        },
        bottomBar = {
            if (signedIn && !vm.needsConsent && page.isEmpty()) NavigationBar {
                tabs.forEachIndexed { index, label ->
                    val count = when (index) { 1 -> vm.inbox.unreadCount; 2 -> vm.friends.requests.size; else -> 0 }
                    NavigationBarItem(selected = tab == index, onClick = { tab = index }, label = { Text(label) },
                        icon = { BadgedBox(badge = { if (count > 0) Badge { Text(count.toString()) } }) { Icon(icons[index], label) } })
                }
            }
        }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            if (vm.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            if (vm.offline && signedIn) Surface(color = MaterialTheme.colorScheme.secondaryContainer) {
                Text("Offline · Showing saved data. Reconnect to make changes.", Modifier.fillMaxWidth().padding(12.dp), style = MaterialTheme.typography.bodySmall)
            }
            when {
                vm.restoring -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = Orange) }
                page == "Privacy Information" -> PrivacyScreen()
                page == "Server Settings" -> ServerScreen(vm) { page = "" }
                page == "Recover Account" && !signedIn -> RecoverScreen(vm)
                !signedIn -> AuthScreen(vm) { page = it }
                page == "Export or Delete My Data" -> AccountDataScreen(vm)
                vm.needsConsent -> Form {
                    PrivacyContent()
                    if (vm.offline) Link("Retry Connection", !vm.busy, onClick = vm::refreshNow)
                    Primary("Accept and Continue", !vm.busy && !vm.offline) { vm.mutate("/v1/consent", body("consent" to true, "consentVersion" to CONSENT_VERSION)) }
                    Link("Export or Delete My Data") { page = "Export or Delete My Data" }
                    Link("Log Out", !vm.busy) { vm.logout() }
                }
                page == "Edit Profile" -> EditProfileScreen(vm) { page = "" }
                page == "Password & Recovery" -> PasswordScreen(vm)
                page == "Active Sessions" -> SessionsScreen(vm)
                page == "Coin History" -> LedgerScreen(vm)
                page == "My Reports" -> ReportsScreen(vm)
                page == "Invitations" -> InvitationsScreen(vm)
                page == "Blocked People" -> BlockedScreen(vm)
                tab == 0 -> PollScreen(vm) { tab = 2 }
                tab == 1 -> InboxScreen(vm)
                tab == 2 -> FriendsScreen(vm) { page = it }
                else -> ProfileScreen(vm) { page = it }
            }
        }
    }
    vm.error?.let { message -> AlertDialog(onDismissRequest = { vm.error = null }, title = { Text("Please try again") },
        text = { Text(message) }, confirmButton = { TextButton(onClick = { vm.error = null }) { Text("OK") } }) }
    vm.recoveryCode?.let { code ->
        var saved by remember(code) { mutableStateOf(false) }
        AlertDialog(onDismissRequest = {}, title = { Text("Save your recovery code") },
            text = { Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                Text("Keep this code somewhere safe. Anyone with your username and this code can take over your account.")
                SelectionContainer { Text(code, fontFamily = FontFamily.Monospace) }
                Text("This replaces your previous code and cannot be shown again after closing.")
                Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(saved, { saved = it }); Text("I saved my recovery code") }
            } }, confirmButton = { TextButton(onClick = vm::dismissRecovery, enabled = saved) { Text("Done") } })
    }
}
