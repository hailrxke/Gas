package app.gas.korea.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.AtomicFile
import android.util.Base64
import java.io.File
import java.security.KeyStore
import java.security.MessageDigest
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

// AES-GCM key stays in Android Keystore; tokens and snapshots live in noBackupFilesDir.
class SecureStore(context: Context) {
    private val root = File(context.noBackupFilesDir, "gas").apply { mkdirs() }
    private fun hash(value: String) = MessageDigest.getInstance("SHA-256").digest(value.toByteArray())
        .joinToString("") { "%02x".format(it) }
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey("gas.v1", null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder("gas.v1", KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    private fun file(id: String) = AtomicFile(File(root, hash(id)))
    private fun write(id: String, value: String?) {
        val file = file(id)
        if (value == null) { file.delete(); return }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()); updateAAD(id.toByteArray()) }
        val payload = Base64.encodeToString(cipher.iv + cipher.doFinal(value.toByteArray()), Base64.NO_WRAP)
        val stream = file.startWrite()
        try { stream.write(payload.toByteArray()); file.finishWrite(stream) }
        catch (e: Exception) { file.failWrite(stream); throw e }
    }
    private fun read(id: String): String? {
        val file = file(id)
        if (!file.baseFile.exists()) return null
        val bytes = Base64.decode(file.readFully(), Base64.NO_WRAP)
        require(bytes.size >= 28) { "Saved session is damaged. Please sign in again." }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply {
            init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, bytes.copyOfRange(0, 12)))
            updateAAD(id.toByteArray())
        }
        return cipher.doFinal(bytes.copyOfRange(12, bytes.size)).toString(Charsets.UTF_8)
    }
    fun token(server: String): String? = read("session:$server")
    fun saveToken(server: String, token: String?) = write("session:$server", token)
    fun clearCache(server: String, token: String) = write("cache:$server\n$token", null)
    fun saveCache(server: String, token: String, snapshot: OfflineSnapshot) =
        write("cache:$server\n$token", WireJson.encodeToString(snapshot))
    fun cache(server: String, token: String): OfflineSnapshot? {
        val snapshot = runCatching { read("cache:$server\n$token")?.let { WireJson.decodeFromString<OfflineSnapshot>(it) } }.getOrNull() ?: return null
        val age = System.currentTimeMillis() - snapshot.savedAt
        if (age !in 0 until 7L * 86400 * 1000) { clearCache(server, token); return null }
        return snapshot
    }
}
