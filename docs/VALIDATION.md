# Validation record

Verified in the Linux workspace on **2026-09-27**:

- **33 automated tests passed**, using Python 3.14.7 and temporary SQLite databases. They cover registration/date/consent validation, stable school identity, recovery-code rotation, password changes and revocation, school changes, invitations, minimum friend count, options beyond the first 15 friends, daily rotation, question snapshots, persistent skips, bounded shuffles, concurrent duplicate votes and atomic rewards, inbox pagination/privacy, blocking/reports, anonymized deletion, export, suspension, persistent sessions, malformed requests, authentication throttling and proxy trust boundaries.
- Operational tests also exercise migration from the original schema with a pre-migration backup, rejection of a newer schema, all-or-nothing school import, mocked NEIS pagination/filtering, operator resolution, retention cleanup, backup integrity, opening a restored database and conservative backup rotation.
- **Real HTTP smoke passed** against Gunicorn 26.2.0 with two workers/two threads, `--preload`, a temporary database and five accounts. It checks school lookup, mutual friendships, persistent skip/restore, a vote and duplicate rejection, points/ledger, anonymous delivery/read count, export, and preserved anonymous history after sender deletion.
- **22 Swift files parsed without syntax errors**, using tree-sitter 0.26.0 and tree-sitter-swift 0.7.3. This is not Swift type checking, Apple SDK validation or an iOS build.
- Xcode generation reproduced identical project files; the plist and shared scheme parse, the content catalog contains 48 questions, and app source remains English. Python static checks (`ruff`, E9/F) and `git diff --check` passed.

Not verified:

- Xcode compilation, simulator execution, signing or any behavior on a real iPhone. This environment has no Xcode/Apple SDK.
- Keychain persistence, file protection, offline UI behavior, share sheets, local notification delivery, VoiceOver/Dynamic Type and actual network transitions on iOS.
- A live NEIS directory download. API credentials have not been supplied; importer tests use synthetic responses matching its documented structure.
- nginx/systemd deployment templates on a provisioned host, public HTTPS, domain setup, scheduled backups/off-host storage or monitoring alerts. Templates and instructions are provided, not installed infrastructure.
- Remote GitHub Actions execution or App Store/TestFlight distribution.

## Reproduce server checks

From the repository root:

```sh
python3 -m unittest discover -s server -v
python3 -m venv .venv
.venv/bin/pip install -r server/requirements.txt
.venv/bin/python scripts/smoke_http.py
```

Tests create isolated databases; they do not use or delete a production database. The migration test explicitly constructs the original schema before starting the updated application. The HTTP script creates and cleans up its own test server/database.

## Required iPhone checks

Use the physical-device setup and five-account walkthrough in [README.md](../README.md). A simulator is optional. On the Mac, first build the `Gas` scheme and fix any compiler errors before installing.

| Scenario | Expected result |
|---|---|
| Registration | Search/select a catalog school, enter an eligible birthday, accept privacy text, save the one-time recovery code |
| Login and relaunch | Session persists in Keychain; profile and school are correct |
| Five-account friendship | A has four accepted friends before polls unlock; unrelated schools cannot connect |
| Questions | 12/day; skip survives relaunch; restore works; change options changes friends when more than four are available |
| Vote under interrupted network | Refresh reconciles the result; retry never awards duplicate points |
| Day boundary | Old `day` receives conflict and refreshes; new round follows Korean midnight |
| Inbox | Search works, Load Older reaches beyond 50, unread badge counts all pages, no sender/timestamp is exposed |
| Password and recovery | Second-device session is revoked after password change/recovery; old recovery code stops working; new code can be saved |
| Session management | Revoking a listed session signs out that session; the current session stays usable |
| Profile and school | Name/login edit persists; school change requires password/confirmation and clears relationships |
| Reports | Sender is blocked without being named; CLI response appears under My Reports; anonymous unblock/reset works |
| Export | Password required; share sheet opens a JSON file without password, token, recovery code or anonymous sender identities |
| Delete account | Password and explicit confirmation required; session/profile removed; recipient keeps an anonymous historical compliment |
| Offline read | After online sync and relaunch without network, profile/friends/first 50 compliments are available; no writes are queued |
| Offline logout | Local session/cache removed; message explains the remote token could not be revoked; revoke it later from another login |
| Server/account isolation | Switching accounts or servers does not show the previous account's cached data |
| Local reminder | Explicit permission; one daily 20:00 reminder, disabled on logout; never claims a new compliment arrived |
| Consent migration | Old account sees current privacy text; export/delete/logout remain available without acceptance |
| Accessibility | Large text, VoiceOver labels, small-screen scrolling and confirmation dialogs remain usable |

Also run the documented restore procedure against a separate staging database and check that timers complete on the selected host. Device success and an actual pilot remain prerequisites for declaring the product ready.
