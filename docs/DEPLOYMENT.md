# Self-hosted deployment

## Process

Use a Linux host with persistent local storage. The standard-library server is for local development; for deployment install the pinned Gunicorn dependency:

```sh
python3 -m venv .venv
.venv/bin/pip install -r server/requirements.txt
GAS_DATABASE=/absolute/path/gas-data/gas.sqlite3 \
  .venv/bin/gunicorn --chdir server --bind 127.0.0.1:8080 \
  --preload --workers 2 --threads 2 --timeout 30 wsgi:application
```

Run as an unprivileged service account. Keep the data directory readable only by that account (directory mode 700, files mode 600; set the process umask to 077). Keep the database outside any static web root. Do not expose the development server to the internet.

Terminate HTTPS with your reverse proxy and a certificate trusted by iOS. Forward requests to the loopback Gunicorn port. Limit request bodies to 16 KiB and set header/body timeouts. Only the proxy should be publicly reachable. No hosting or domain has been provisioned by this repository.

The API's login limit uses the directly connected IP, ignoring untrusted forwarded headers. Behind a reverse proxy this means requests share the proxy IP budget (30 attempts per 10 minutes). For a larger deployment implement trusted-proxy client-IP handling and edge rate limits before increasing that budget. For a small private pilot the conservative shared limit is intentional.

Configure the iOS login screen with the HTTPS base URL (without `/v1`). Credentials and sessions belong to that server. Do not point the app at an untrusted server.

## Backups

Use SQLite's backup API, not a live copy of only the `.sqlite3` file while WAL is active:

```sh
python3 - /absolute/path/gas-data/gas.sqlite3 /secure/backup/gas.sqlite3 <<'PY'
import sqlite3, sys
with sqlite3.connect(sys.argv[1]) as source, sqlite3.connect(sys.argv[2]) as target:
    source.backup(target)
PY
```

Test restoration into a separate database with the API stopped. Define a retention period for backups and exclude expired backups when processing account deletion. SQLite on a single local disk is intended for a small MVP; do not put its WAL database on a network filesystem or run independently replicated copies.

## Reports

Reports immediately hide the sender's compliments and remove the friendship. They also create an operator review record. There is no automatic moderation decision or staffed review service.

Review records locally on the server (operator access to the database is required):

```sh
python3 server/manage.py reports --database /absolute/path/gas-data/gas.sqlite3
```

To revoke all current sessions of a reported account:

```sh
python3 server/manage.py revoke USER_ID --database /absolute/path/gas-data/gas.sqlite3
```

Revocation signs out existing sessions; it does not ban future logins. For a public pilot, provide a contact channel and define a moderation process before inviting users. Never expose the database or report output as a public download: operators can identify senders in this data.

## Sources

- [Python WSGI development server](https://docs.python.org/3/library/wsgiref.html)
- [Gunicorn installation and deployment](https://gunicorn.org/quickstart/)
- [Apple App Transport Security](https://developer.apple.com/documentation/BundleResources/Information-Property-List/NSAppTransportSecurity)
- [Apple Keychain accessibility](https://developer.apple.com/documentation/security/ksecattraccessiblewhenunlockedthisdeviceonly)
