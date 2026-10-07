package app.gas.korea.data

import java.net.URI
import java.util.Locale

object ServerAddress {
    const val guidance = "Use an HTTPS server address without /health or /v1. Debug builds also allow local HTTP (emulator: http://10.0.2.2:8080)."

    fun normalize(value: String, debug: Boolean): String {
        val cleaned = value.trim().trimEnd('/')
        val uri = try { URI(cleaned) } catch (_: Exception) { throw IllegalArgumentException(guidance) }
        val host = uri.host?.lowercase(Locale.ROOT) ?: throw IllegalArgumentException(guidance)
        val scheme = uri.scheme?.lowercase(Locale.ROOT)
        require(uri.rawUserInfo == null && uri.rawQuery == null && uri.rawFragment == null &&
            uri.rawPath.isNullOrEmpty() && (uri.port == -1 || uri.port in 1..65535) &&
            !uri.rawAuthority.endsWith(':') &&
            (scheme == "https" || (scheme == "http" && debug && isLocal(host)))) { guidance }
        return URI(scheme, null, host, uri.port, null, null, null).toASCIIString()
    }

    private fun isLocal(host: String): Boolean {
        if (host == "localhost" || host == "127.0.0.1" || host == "[::1]" || host.endsWith(".local")) return true
        val parts = host.split('.')
        val octets = parts.mapNotNull { it.toIntOrNull() }
        if (parts.size != 4 || octets.size != 4 || parts.zip(octets).any { (part, n) -> n !in 0..255 || part != n.toString() }) return false
        return octets[0] == 10 || (octets[0] == 172 && octets[1] in 16..31) ||
            (octets[0] == 192 && octets[1] == 168)
    }
}
