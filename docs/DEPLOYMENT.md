# Self-hosted deployment

The repository includes deployment templates; it has not provisioned hosting, certificates, a domain or a staffed moderation service. Use persistent local storage and an unprivileged account. Keep the data directory outside the web root, mode 700, and use umask 077. SQLite is intended for a small single-host pilot, not independent replicas or a network filesystem.

## School catalog

Registration requires an active catalog entry. For local testing only:

```sh
python3 server/manage.py init
python3 server/manage.py import-schools server/examples/schools.json
```

For your own reviewed catalog, import a JSON array or CSV with these fields:

```json
[
  {
    "id": "your-stable-school-id",
    "name": "School name",
    "englishName": "Optional English name",
    "region": "City or region",
    "address": "Optional address",
    "kind": "Optional school type"
  }
]
```

`id`, `name`, `region` are required strings; IDs must be unique. The importer validates the whole batch before writing and upserts by ID. Omitted schools are not deactivated automatically. Keep IDs stable when renaming schools. School selection does not verify enrollment.

To obtain Korean secondary schools from the official [NEIS school directory](https://open.neis.go.kr/portal/data/service/selectServicePage.do?infId=OPEN17020190531110010104913&infSeq=2), obtain your own API key and set `NEIS_API_KEY` in the process environment, then run:

```sh
python3 server/import_neis.py neis-schools.json
python3 server/manage.py import-schools neis-schools.json
```

The downloader paginates the NEIS `schoolInfo` endpoint, selects middle/high schools and derives stable IDs from education-office and school codes. `--region B10` limits the download to an office. The output contains no key. Do not paste keys into source code, command history or Git. No full live download has been performed here: tests use recorded-format synthetic responses. Proper school names remain in the source language; the app uses the provided English name when available and English UI labels throughout.

## Process and HTTPS

Commands from the repository root:

```sh
python3 -m venv .venv
.venv/bin/pip install -r server/requirements.txt
GAS_DATABASE=/absolute/path/gas-data/gas.sqlite3 \
  .venv/bin/gunicorn --chdir server --bind 127.0.0.1:8080 \
  --preload --workers 2 --threads 2 --timeout 30 wsgi:application
```

`--preload` initializes/migrates the application once before worker startup. Run only one migration process; stop the service before upgrading the schema. The development `server/app.py` runner is for local testing.

[deploy/gas.service](../deploy/gas.service) assumes source at `/opt/gas`, a pre-created `gas` user/group, data at `/var/lib/gas`, and `/etc/gas.env` based on [gas.env.example](../deploy/gas.env.example). Adapt paths, ownership and Python environment before installing the unit. Install the service only after importing your school catalog into **the same database** named by `GAS_DATABASE`.

[deploy/nginx.conf.example](../deploy/nginx.conf.example) is a TLS reverse-proxy template. Replace domain and certificate paths, obtain a certificate trusted by iOS, and validate it with `nginx -t`. Restrict the API port to loopback; only HTTPS should be reachable publicly. The template disables access logs to avoid recording query strings and overwrites `X-Real-IP`. Check your nginx error-log retention separately.

Use `GAS_TRUSTED_PROXIES=127.0.0.1` only when the proxy is on loopback and overwrites the header. Without this setting, the API ignores forwarded addresses and shares one rate budget for clients behind the proxy. Do not trust broad networks or publicly reachable clients. For an upstream load balancer/CDN, define the real-IP trust boundary before adapting this template; it is not included here.

The API logs request ID, method, status and duration, without request body, URL query, token or IP. Keep exception logs private. `/health` checks database availability and returns schema version; external uptime monitoring and alert routing must be configured by the operator.

## Updating the original database

1. Stop old application workers and take a separate SQLite backup.
2. Install the new code, then run:

   ```sh
   python3 server/manage.py --database /absolute/path/gas.sqlite3 init
   ```

3. Migration from the original schema creates `/absolute/path/gas.sqlite3.pre-v2.bak` without overwriting an existing backup, then applies transactional schema changes and foreign-key checks. The database records `PRAGMA user_version=2`; repeated startup does not remigrate it. Newer unknown schema versions are rejected.
4. Import the catalog. Legacy school strings become inactive `legacy-*` groups, preserving existing relationships. Inspect local IDs, then map each reviewed group:

   ```sh
   python3 server/manage.py --database /absolute/path/gas.sqlite3 map-school LEGACY_ID ACTIVE_SCHOOL_ID
   ```

5. Deploy the updated client and start the server. Registration now sends `schoolId`/`birthDate`/consent, and voting sends `day`. Old clients are incompatible with these writes.

Do not guess a birthday for migrated accounts. Their old stated age remains until a future birthday-update flow is added. They can create a recovery code after authenticating and must accept the current privacy text before using social/poll routes. Historical balances receive an opening-ledger entry; historical questions receive a stored text snapshot.

For rollback, stop the service and restore both the old code and its pre-migration database. Do not run old code against schema 2. Securely remove/move obsolete migration backups according to your backup policy: daily rotation below intentionally does not delete `.pre-v2.bak` files.

## Backups and retention

Use SQLite's backup API; do not copy just the main file while the database is live:

```sh
python3 server/manage.py --database /absolute/path/gas.sqlite3 \
  backup /secure/backup/manual-backup.sqlite3
```

The command refuses to overwrite a destination, creates it with mode 600 and runs `PRAGMA integrity_check`. To back up, prune expired records and rotate this tool's daily backups:

```sh
python3 scripts/maintenance.py \
  --database /absolute/path/gas.sqlite3 \
  --backups /secure/backups --keep-days 7
```

Cleanup starts only after backup succeeds. It removes expired sessions/invitations, rate counters older than a day, poll offers/exposure counts older than 30 Korean calendar days, activity events older than 90 days, reports/audit older than 90 days, and votes older than 365 days. Account profiles and coin ledgers are retained until account deletion. The balance is not reset when voting history expires. Anonymous block reset remains available even after the associated reports expire.

Rotation affects only valid `gas-backup-<timestamp>.sqlite3` filenames created by this script. It leaves manual files, symlinks and migration backups alone. A local backup does not protect against disk loss: arrange a protected off-host copy with its own expiry policy.

[gas-maintenance.service](../deploy/gas-maintenance.service) and [gas-maintenance.timer](../deploy/gas-maintenance.timer) schedule this once a day after the operator installs/enables them. Their templates use `/var/lib/gas/backups` and seven days. They are not installed by running the development server. Inspect timer results and failed services; no external alerts are configured.

Test restoration with the service stopped: restore into a new directory with mode 700, check `integrity_check` and `foreign_key_check`, then point a staging server at the restored database. Never blindly overwrite a live WAL database or leave WAL/SHM files from a different database alongside a restored file. Backups retain deleted information until they expire; document that period and repeat deletion requests after disaster recovery where applicable.

## Moderation and metrics

Run as the database owner. Put `--database` **before** the subcommand:

```sh
python3 server/manage.py --database /absolute/path/gas.sqlite3 reports
python3 server/manage.py --database /absolute/path/gas.sqlite3 \
  resolve REPORT_ID --status action_taken --message 'Reviewed; account restrictions applied.'
python3 server/manage.py --database /absolute/path/gas.sqlite3 \
  suspend USER_ID --reason 'Reviewed abuse report'
python3 server/manage.py --database /absolute/path/gas.sqlite3 unsuspend USER_ID
python3 server/manage.py --database /absolute/path/gas.sqlite3 revoke USER_ID
python3 server/manage.py --database /absolute/path/gas.sqlite3 metrics
```

`resolve` sets a public response; **do not put the sender's identity in it**. Resolution does not automatically suspend an account: run `suspend` separately when appropriate. Suspension revokes sessions, excludes the account from discovery/options and prevents login/recovery until lifted. `revoke` signs out existing sessions without banning future logins. These actions are audited locally. CLI/database access is privileged; no web administrator interface is exposed.

Metrics report daily unique registrations, active users, connected users, voters, open reports and D1/D7 return cohorts. Events are recorded by server actions and the app's active refresh, retained for 90 days, and deleted with the account. Thus cohorts are operational estimates, not immutable business accounting. There is no external analytics SDK or crash-reporting service.

## What still requires an operator

Provide a contact channel, review reports, choose retention appropriate for your service, validate the privacy text, obtain the school source/API access, configure a trusted HTTPS host, and test the updated iOS build. Optional email/SMS delivery, APNs remote notifications, photo storage/moderation and payments are not provisioned or implemented. Daily reminders use only local iOS notifications.
