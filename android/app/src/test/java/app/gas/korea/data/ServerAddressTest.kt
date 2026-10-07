package app.gas.korea.data

import org.junit.Assert.*
import org.junit.Test

class ServerAddressTest {
    @Test fun normalizesOrigin() {
        assertEquals("https://example.com:8443", ServerAddress.normalize(" HTTPS://EXAMPLE.COM:8443/ ", false))
        assertEquals("http://10.0.2.2:8080", ServerAddress.normalize("http://10.0.2.2:8080/", true))
    }
    @Test fun debugOnlyAllowsLocalHttp() {
        listOf("localhost", "127.0.0.1", "[::1]", "dev.local", "10.12.249.108", "172.16.0.1", "172.31.255.254", "192.168.1.2").forEach {
            ServerAddress.normalize("http://$it:8080", true)
        }
        listOf("example.com", "8.8.8.8", "172.15.0.1", "172.32.0.1", "192.169.1.1", "10.01.2.3", "localhost.evil.com").forEach {
            assertThrows(IllegalArgumentException::class.java) { ServerAddress.normalize("http://$it", true) }
        }
    }
    @Test fun releaseRequiresHttps() {
        listOf("localhost", "10.0.2.2", "127.0.0.1", "dev.local").forEach {
            assertThrows(IllegalArgumentException::class.java) { ServerAddress.normalize("http://$it", false) }
        }
    }
    @Test fun rejectsCredentialsPathsQueriesAndInvalidPorts() {
        listOf("", "example.com", "ftp://example.com", "https://user:pass@example.com", "https://example.com/health",
            "https://example.com/v1", "https://example.com?token=secret", "https://example.com#fragment", "https://example.com:0",
            "https://example.com:65536", "https://example.com:", "https://example.com/a/..").forEach {
            assertThrows(it, IllegalArgumentException::class.java) { ServerAddress.normalize(it, true) }
        }
    }
}
