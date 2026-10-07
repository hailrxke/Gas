@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
package app.gas.korea.ui

import android.app.DatePickerDialog
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.gas.korea.GasViewModel
import app.gas.korea.data.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import java.time.LocalDate

@Composable fun AuthScreen(vm: GasViewModel, navigate: (String) -> Unit) {
    var register by rememberSaveable { mutableStateOf(false) }
    var username by rememberSaveable { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var confirmation by remember { mutableStateOf("") }
    var name by rememberSaveable { mutableStateOf("") }
    var school by remember { mutableStateOf<School?>(null) }
    var birthDate by rememberSaveable { mutableStateOf(LocalDate.now().minusYears(16).toString()) }
    var consent by rememberSaveable { mutableStateOf(false) }
    var privacy by remember { mutableStateOf(false) }
    LaunchedEffect(vm.server) { school = null }
    Form {
        Text("🔥 GAS", fontSize = 46.sp, fontWeight = FontWeight.Black, color = Orange)
        Text("Give a friend a little boost", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Hint("Connect with friends and send anonymous compliments.")
        if (vm.hasSession) {
            Group {
                Text("Your session is saved. Reconnect to finish loading your account.")
                Primary("Retry Connection", !vm.busy, vm::retrySession)
                Link("Log Out on This Device", !vm.busy) { vm.logout() }
            }
        } else {
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                listOf("Log In", "Sign Up").forEachIndexed { index, text ->
                    SegmentedButton(selected = register == (index == 1), onClick = { register = index == 1 },
                        shape = SegmentedButtonDefaults.itemShape(index, 2)) { Text(text) }
                }
            }
            Group {
                Field("Username", username, { username = it })
                Field("Password", password, { password = it }, secret = true)
                if (register) Field("Confirm password", confirmation, { confirmation = it }, secret = true)
                Hint("Usernames: 3–24 letters, numbers or underscores. Passwords: 10–128 characters.")
            }
            if (register) {
                Group("Profile") {
                    Field("Name or nickname", name, { name = it })
                    SchoolField(vm, school) { school = it }
                    BirthdayField(birthDate) { birthDate = it }
                    Hint("GAS is for ages 14–19. Your birthday is private; school and age are self-reported.")
                }
                Group {
                    Link("Privacy Information") { privacy = true }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(consent, { consent = it })
                        Text("I have read the privacy information and agree to create an account and use the service.")
                    }
                }
            }
            Primary(if (register) "Create Account" else "Log In", !vm.busy && validUsername(username) && validPassword(password) &&
                (!register || (name.trim().isNotBlank() && name.codePointCount(0, name.length) <= 40 && school != null && password == confirmation && consent))) {
                vm.authenticate(register, username, password, name, school?.id ?: "", birthDate)
            }
            Link("Forgot password?") { navigate("Recover Account") }
        }
        Link("Server Settings", !vm.busy && !vm.hasSession) { navigate("Server Settings") }
    }
    if (privacy) ModalBottomSheet(onDismissRequest = { privacy = false }) {
        Box(Modifier.fillMaxHeight(0.9f)) { PrivacyScreen() }
    }
}

@Composable fun ServerScreen(vm: GasViewModel, done: () -> Unit) {
    var address by rememberSaveable { mutableStateOf(vm.server) }
    Form {
        Group {
            Field("Server address", address, { address = it })
            Hint(ServerAddress.guidance)
            Hint("On a physical phone, use your server computer's LAN address. localhost means the phone itself.")
        }
        Primary("Save", !vm.busy) { vm.configure(address, done) }
    }
}

@Composable fun RecoverScreen(vm: GasViewModel) {
    var username by rememberSaveable { mutableStateOf("") }
    var code by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var confirmation by remember { mutableStateOf("") }
    Form {
        Hint("Use your saved recovery code to reset your password. This signs out every other device and gives you a new code.")
        Group {
            Field("Username", username, { username = it })
            Field("Recovery code", code, { code = it })
            Field("New password", password, { password = it }, secret = true)
            Field("Confirm password", confirmation, { confirmation = it }, secret = true)
        }
        Primary("Reset Password", !vm.busy && validUsername(username) && code.length >= 32 && validPassword(password) && password == confirmation) {
            vm.replaceSession("/v1/recover", body("username" to username, "recoveryCode" to code, "newPassword" to password)) { code = ""; password = ""; confirmation = "" }
        }
        Hint("Without your password or saved recovery code, automatic recovery is unavailable.")
    }
}

@Composable fun BirthdayField(value: String, change: (String) -> Unit) {
    val context = LocalContext.current
    OutlinedButton(onClick = {
        val date = LocalDate.parse(value)
        DatePickerDialog(context, { _, year, month, day -> change(LocalDate.of(year, month + 1, day).toString()) },
            date.year, date.monthValue - 1, date.dayOfMonth).show()
    }, modifier = Modifier.fillMaxWidth()) { Text("Date of birth: $value") }
}

@Composable fun SchoolField(vm: GasViewModel, selection: School?, fallback: String = "Choose School", select: (School) -> Unit) {
    var open by remember { mutableStateOf(false) }
    OutlinedButton(onClick = { open = true }, modifier = Modifier.fillMaxWidth()) { Text(selection?.displayName ?: fallback) }
    if (open) ModalBottomSheet(onDismissRequest = { open = false }) {
        var query by remember { mutableStateOf("") }
        var schools by remember { mutableStateOf<List<School>>(emptyList()) }
        var loading by remember { mutableStateOf(false) }
        var error by remember { mutableStateOf<String?>(null) }
        var retry by remember { mutableIntStateOf(0) }
        LaunchedEffect(query, retry) {
            loading = true; error = null
            try { delay(300); schools = vm.schools(query) }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) { error = e.message ?: "Could not load schools." }
            finally { loading = false }
        }
        Column(Modifier.fillMaxWidth().fillMaxHeight(0.85f).imePadding().padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Choose School", style = MaterialTheme.typography.headlineSmall)
            Field("Search schools or region", query, { query = it })
            Hint("Choose your school from the catalog. This does not verify enrollment.")
            if (loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            error?.let { Hint(it); Link("Retry") { retry++ } }
            if (!loading && error == null && schools.isEmpty()) Hint("No schools found. Try another name or region.")
            LazyColumn {
                items(schools, key = { it.id }) { school ->
                    ListItem(headlineContent = { Text(school.displayName) },
                        supportingContent = { Text(listOf(school.region, school.address, school.kind).filter { it.isNotBlank() }.joinToString(" · ")) },
                        modifier = Modifier.clickable { select(school); open = false })
                    HorizontalDivider()
                }
            }
        }
    }
}
