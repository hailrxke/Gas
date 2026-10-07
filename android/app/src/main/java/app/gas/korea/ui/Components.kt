package app.gas.korea.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp

val Orange = Color(0xFFFF851B)
val Pink = Color(0xFFED6D98)

@Composable fun GasTheme(content: @Composable () -> Unit) {
    val colors = if (isSystemInDarkTheme()) darkColorScheme(primary = Orange, secondary = Pink,
        background = Color(0xFF171619), surface = Color(0xFF232126))
    else lightColorScheme(primary = Color(0xFFAA4800), secondary = Color(0xFFAD315E),
        primaryContainer = Color(0xFFFFE1C7), onPrimaryContainer = Color(0xFF512000),
        background = Color(0xFFF5F4F8), surface = Color.White)
    MaterialTheme(colorScheme = colors, content = content)
}

@Composable fun Form(content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp), content = content)
}

@Composable fun Group(title: String? = null, content: @Composable ColumnScope.() -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        title?.let { Text(it, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp), content = content)
        }
    }
}

@Composable fun Field(label: String, value: String, onChange: (String) -> Unit,
                      secret: Boolean = false, enabled: Boolean = true, keyboard: KeyboardType = KeyboardType.Text) {
    OutlinedTextField(value, onChange, Modifier.fillMaxWidth(), label = { Text(label) },
        enabled = enabled, singleLine = true, shape = RoundedCornerShape(14.dp),
        visualTransformation = if (secret) PasswordVisualTransformation() else VisualTransformation.None,
        keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.None,
            autoCorrectEnabled = false, keyboardType = if (secret) KeyboardType.Password else keyboard))
}

@Composable fun Primary(label: String, enabled: Boolean = true, onClick: () -> Unit) {
    Button(onClick, Modifier.fillMaxWidth().heightIn(min = 52.dp), enabled = enabled,
        shape = RoundedCornerShape(16.dp), colors = ButtonDefaults.buttonColors(containerColor = Orange, contentColor = Color(0xFF301300))) {
        Text(label, fontWeight = FontWeight.Bold)
    }
}

@Composable fun Link(label: String, enabled: Boolean = true, danger: Boolean = false, onClick: () -> Unit) {
    TextButton(onClick, enabled = enabled, contentPadding = PaddingValues(horizontal = 0.dp, vertical = 8.dp)) {
        Text(label, color = if (danger) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
    }
}

@Composable fun Hint(text: String) { Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }

@Composable fun Confirm(title: String, message: String, label: String, dismiss: () -> Unit, action: () -> Unit) {
    AlertDialog(onDismissRequest = dismiss, title = { Text(title) }, text = { Text(message) },
        confirmButton = { TextButton(onClick = { dismiss(); action() }) { Text(label) } },
        dismissButton = { TextButton(onClick = dismiss) { Text("Cancel") } })
}

fun validUsername(value: String) = Regex("^[a-zA-Z0-9_]{3,24}$").matches(value)
fun validPassword(value: String) = value.codePointCount(0, value.length) in 10..128
