@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
package app.gas.korea.ui

import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.gas.korea.GasViewModel
import app.gas.korea.data.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

@Composable fun PollScreen(vm: GasViewModel, showFriends: () -> Unit) {
    val polls = vm.polls
    val poll = polls.polls.firstOrNull()
    val enabled = !vm.busy && !vm.offline && vm.pollReady
    Box(Modifier.fillMaxSize().background(Brush.linearGradient(listOf(Orange, Pink)))) {
        Form {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Today: ${polls.answered} / ${polls.total}", fontWeight = FontWeight.Bold, color = Color(0xFF301326))
                Text("★ ${vm.user?.coins ?: 0}", fontWeight = FontWeight.Bold, color = Color(0xFF301326))
            }
            LinearProgressIndicator(progress = { if (polls.total == 0) 0f else polls.answered.toFloat() / polls.total },
                modifier = Modifier.fillMaxWidth(), color = Color.White, trackColor = Color.White.copy(alpha = 0.3f))
            Spacer(Modifier.height(16.dp))
            when {
                !vm.pollReady -> Group {
                    Text("Ready for a little positivity?", style = MaterialTheme.typography.headlineMedium)
                    Hint("Connect to load today's polls.")
                    Primary("Load Polls", !vm.busy, vm::refreshNow)
                }
                poll != null -> {
                    Text(poll.emoji, Modifier.fillMaxWidth(), fontSize = 80.sp, textAlign = TextAlign.Center)
                    Text(poll.question, Modifier.fillMaxWidth(), style = MaterialTheme.typography.headlineLarge,
                        fontWeight = FontWeight.Bold, textAlign = TextAlign.Center, color = Color(0xFF301326))
                    Spacer(Modifier.height(12.dp))
                    poll.options.chunked(2).forEach { row ->
                        Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                            row.forEach { option ->
                                Button(onClick = { vm.vote(option) }, enabled = enabled,
                                    modifier = Modifier.weight(1f).heightIn(min = 86.dp), shape = RoundedCornerShape(20.dp),
                                    colors = ButtonDefaults.buttonColors(containerColor = Color.White, contentColor = Color(0xFF302731))) {
                                    Text(option.userName, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
                                }
                            }
                        }
                    }
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                        TextButton(onClick = { vm.changePoll("skip") }, enabled = enabled) { Text("Skip", color = Color(0xFF301326)) }
                        TextButton(onClick = { vm.changePoll("shuffle") }, enabled = enabled && polls.friendCount > 4) {
                            Text("Change options", color = Color(0xFF301326))
                        }
                    }
                    Text("Your pick stays anonymous. +20 coins per answer.", Modifier.fillMaxWidth(),
                        textAlign = TextAlign.Center, color = Color(0xFF301326), style = MaterialTheme.typography.bodySmall)
                }
                polls.friendCount < polls.minimumFriends -> Group {
                    Text("Bring your friends 🔥", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                    Hint("You need ${polls.minimumFriends} accepted friends to unlock polls. You have ${polls.friendCount} so far.")
                    Primary("Find Friends", onClick = showFriends)
                }
                else -> Group {
                    Text("You're all caught up 🎉", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                    Hint("Come back tomorrow for more compliments. A new day starts at midnight in Korea.")
                }
            }
            if (polls.skipped > 0) OutlinedButton(onClick = { vm.changePoll("restore") }, enabled = enabled, modifier = Modifier.fillMaxWidth()) {
                Text("Restore ${polls.skipped} skipped polls", color = Color(0xFF301326))
            }
        }
    }
}

@Composable fun InboxScreen(vm: GasViewModel) {
    var reporting by remember { mutableStateOf<Flame?>(null) }
    val visible = if (vm.offline && vm.inboxQuery.isNotBlank()) vm.inbox.flames.filter { it.pollQuestion.contains(vm.inboxQuery, true) } else vm.inbox.flames
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item { Field("Search compliments", vm.inboxQuery, vm::searchInbox) }
        if (visible.isEmpty()) item { Group {
            Text(if (vm.inboxQuery.isBlank()) "No compliments yet" else "No matching compliments", style = MaterialTheme.typography.titleLarge)
            Hint("When a friend picks you, their compliment will appear here.")
        } }
        items(visible, key = { it.id }) { flame -> Group {
            Text("🔥 A friend picked you${if (!flame.isRead) " · NEW" else ""}", fontWeight = FontWeight.Bold)
            Text(flame.pollQuestion, style = MaterialTheme.typography.titleLarge)
            Hint(flame.day)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                if (!flame.isRead) Link("Mark as read", !vm.busy && !vm.offline) { vm.mutate("/v1/inbox/read", body("id" to flame.id)) }
                Link("Report & Block", !vm.busy && !vm.offline, danger = true) { reporting = flame }
            }
        } }
        if (vm.inbox.nextCursor != null) item { Primary("Load Older Compliments", !vm.busy && !vm.offline, vm::loadOlder) }
    }
    reporting?.let { flame ->
        var reason by remember { mutableStateOf("") }
        AlertDialog(onDismissRequest = { if (!vm.busy) reporting = null }, title = { Text("Report & Block") },
            text = { Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("We will record your report and hide this sender's compliments. Their identity will stay hidden.")
                OutlinedTextField(reason, { reason = it }, label = { Text("Reason (3–500 characters)") })
            } }, confirmButton = {
                TextButton(onClick = { vm.mutate("/v1/reports", body("id" to flame.id, "reason" to reason)) { reporting = null } },
                    enabled = reason.trim().length in 3..500 && !vm.busy) { Text("Report & Block") }
            }, dismissButton = { TextButton(onClick = { reporting = null }, enabled = !vm.busy) { Text("Cancel") } })
    }
}

@Composable fun FriendsScreen(vm: GasViewModel, navigate: (String) -> Unit) {
    var query by rememberSaveable { mutableStateOf("") }
    var people by remember { mutableStateOf<List<User>>(emptyList()) }
    var searching by remember { mutableStateOf(false) }
    var failure by remember { mutableStateOf<String?>(null) }
    var retry by remember { mutableIntStateOf(0) }
    var blocking by remember { mutableStateOf<User?>(null) }
    var removing by remember { mutableStateOf<User?>(null) }
    LaunchedEffect(query, vm.friends, retry) {
        people = emptyList(); failure = null
        if (query.trim().length < 2) return@LaunchedEffect
        searching = true
        try { delay(300); people = vm.people(query.trim()) }
        catch (e: CancellationException) { throw e }
        catch (e: Exception) { failure = e.message ?: "Search failed." }
        finally { searching = false }
    }
    val enabled = !vm.busy && !vm.offline
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) {
            Link("Invitations") { navigate("Invitations") }; Link("Blocked People") { navigate("Blocked People") }
        } }
        item { Field("Search your school (2+ characters)", query, { query = it }) }
        if (searching) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
        failure?.let { item { Hint(it); Link("Retry") { retry++ } } }
        if (query.trim().length >= 2) {
            if (!searching && failure == null && people.isEmpty()) item { Hint("No schoolmates found.") }
            items(people, key = { "search:${it.id}" }) { person -> PersonCard(person) {
                val accepted = vm.friends.friends.any { it.id == person.id }
                val sent = vm.friends.sent.any { it.id == person.id }
                val incoming = vm.friends.requests.any { it.id == person.id }
                when {
                    accepted -> Hint("Friends")
                    sent -> Hint("Request sent")
                    else -> Link(if (incoming) "Accept" else "Add Friend", enabled) { vm.mutate("/v1/friends", body("userId" to person.id)) }
                }
                Link("Block", enabled, danger = true) { blocking = person }
            } }
        }
        if (vm.friends.requests.isNotEmpty()) item { Text("Friend Requests", style = MaterialTheme.typography.titleLarge) }
        items(vm.friends.requests, key = { "request:${it.id}" }) { person -> PersonCard(person) {
            Link("Accept", enabled) { vm.mutate("/v1/friends", body("userId" to person.id)) }
            Link("Decline", enabled) { vm.mutate("/v1/friends", body("userId" to person.id), "DELETE") }
        } }
        item { Text("Friends · ${vm.friends.friends.size}", style = MaterialTheme.typography.titleLarge) }
        if (vm.friends.friends.isEmpty()) item { Hint("Search for schoolmates or share an invitation. Both people must accept before voting.") }
        items(vm.friends.friends, key = { "friend:${it.id}" }) { person -> PersonCard(person) {
            Link("Remove", enabled) { removing = person }
            Link("Block", enabled, danger = true) { blocking = person }
        } }
        if (vm.friends.sent.isNotEmpty()) item { Text("Sent Requests", style = MaterialTheme.typography.titleLarge) }
        items(vm.friends.sent, key = { "sent:${it.id}" }) { person -> PersonCard(person) {
            Link("Cancel Request", enabled) { vm.mutate("/v1/friends", body("userId" to person.id), "DELETE") }
        } }
    }
    blocking?.let { person -> Confirm("Block ${person.name}?", "This removes your friendship and hides their compliments.", "Block", { blocking = null }) {
        vm.mutate("/v1/blocks", body("userId" to person.id))
    } }
    removing?.let { person -> Confirm("Remove ${person.name}?", "You will need a new accepted friend request to reconnect.", "Remove", { removing = null }) {
        vm.mutate("/v1/friends", body("userId" to person.id), "DELETE")
    } }
}

@Composable private fun PersonCard(person: User, actions: @Composable RowScope.() -> Unit) {
    Group {
        Text(person.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Hint("@${person.username}")
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, content = actions)
    }
}

@Composable fun BlockedScreen(vm: GasViewModel) {
    Form {
        Hint("Unblocking does not restore a friendship. Anonymous sender blocks are managed in My Reports.")
        if (vm.blocked.isEmpty()) Hint("No named blocks.")
        vm.blocked.forEach { person -> PersonCard(person) {
            Link("Unblock", !vm.busy && !vm.offline) { vm.mutate("/v1/blocks", body("userId" to person.id), "DELETE") }
        } }
    }
}

@Composable fun InvitationsScreen(vm: GasViewModel) {
    val context = LocalContext.current
    var invitation by remember { mutableStateOf<Invitation?>(null) }
    var code by rememberSaveable { mutableStateOf("") }
    Form {
        Group("Invite a schoolmate") {
            Hint("Codes expire after seven days. Creating a new one replaces the old code. Both people still need to accept the friendship.")
            Primary("Create New Invitation", !vm.busy && !vm.offline) {
                vm.fetch({ it.post<Invitation>("/v1/invites", body()) }) { invitation = it }
            }
            invitation?.let { invite ->
                SelectionContainer { Text(invite.code, style = MaterialTheme.typography.headlineSmall) }
                Hint("Expires: ${formatTime(invite.expires)}")
                Link("Share Invitation") {
                    context.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("text/plain")
                        .putExtra(Intent.EXTRA_TEXT, "Join me on GAS! In Friends → Invitations, enter: ${invite.code}\nChoose my school and use the same server: ${vm.server}"), "Share Invitation"))
                }
            }
        }
        Group("Have an invitation?") {
            Field("Invitation code", code, { code = it })
            Primary("Send Friend Request", !vm.busy && !vm.offline && code.isNotBlank()) {
                vm.mutate("/v1/invites/accept", body("code" to code.trim())) { code = ""; vm.notice = "Request sent. Check Friends for its status." }
            }
        }
    }
}

fun formatTime(seconds: Double): String = if (seconds <= 0) "Unavailable" else
    DateTimeFormatter.ofPattern("MMM d, yyyy · HH:mm").withZone(ZoneId.systemDefault()).format(Instant.ofEpochSecond(seconds.toLong()))
