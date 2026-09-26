# API contract (schema 2)

JSON bodies, max 16 KiB. Authenticated routes use `Authorization: Bearer <token>`. All responses use `Cache-Control: no-store` and `X-Request-ID`. Errors contain `error` and `requestId`; 429/503 include `Retry-After`. Tokens expire after 30 days. Passwords preserve whitespace and must contain 10–128 characters. Usernames are case-insensitive ASCII letters, digits and underscores, 3–24 characters.

This revision changes the registration and voting contracts. Deploy the updated iOS client and server together.

## Accounts and schools

| Method | Path | Body/query | Response |
|---|---|---|---|
| GET | `/health` | Public | `status`, `schemaVersion` |
| GET | `/v1/config` | Public | `consentVersion`, `minimumFriends` |
| GET | `/v1/schools` | Public, optional `q` | `schools`, at most 50 |
| POST | `/v1/register` | `username`, `password`, `name`, `schoolId`, `birthDate`, `consent: true`, `consentVersion`; optional `deviceName` | `token`, one-time `recoveryCode` |
| POST | `/v1/login` | `username`, `password`; optional `deviceName` | `token` |
| POST | `/v1/recover` | `username`, `recoveryCode`, `newPassword`; optional `deviceName` | new `token`, new `recoveryCode`; all prior sessions revoked |
| GET | `/v1/me` | — | Own profile |
| PATCH | `/v1/me` | `name`, `username`, `schoolId`; a school change also requires `password`, `confirmSchoolChange: true` | `ok` |
| DELETE | `/v1/me` | `password` | `ok` |
| POST | `/v1/logout` | `{}` | `ok` |
| POST | `/v1/password` | `password`, `newPassword`; optional `deviceName` | new `token`, new `recoveryCode`; all prior sessions revoked |
| POST | `/v1/recovery-code` | `password` | new one-time `recoveryCode` |
| GET | `/v1/sessions` | — | `sessions`: `id`, `device`, `created`, `expires`, `current` |
| DELETE | `/v1/sessions` | `id` or `allOthers: true` | `ok`; use logout for current session |
| POST | `/v1/consent` | `consent: true`, `consentVersion` | `ok` |
| POST | `/v1/export` | `password` | JSON data export, no credentials or anonymous sender identities |
| POST | `/v1/activity` | `{}` | `ok`; records at most one active event per account/Korean day |

Registration example (choose an active school ID from the catalog and an eligible birth date):

```json
{
  "username": "student_a",
  "password": "a long unique password",
  "name": "Alex",
  "schoolId": "demo:school-a",
  "birthDate": "2010-01-01",
  "consent": true,
  "consentVersion": "2026-09-27"
}
```

School objects: `id`, `name`, `englishName`, `region`, `address`, `kind`. IDs, not names, define school membership. Search normalizes Unicode/whitespace/case and matches part of the catalog text. A catalog entry is not proof of enrollment. Birth dates use `YYYY-MM-DD`; age 14–19 is checked at registration against Korea's date. Existing legacy profiles can have `birthDate: null`.

Public user objects: `id`, `username`, `name`, `school`, `schoolId`. Own profiles add `age`, `birthDate`, `coins`, `hasRecoveryCode`, `consentVersion`. No other user's birthday, balance or credentials are returned. A profile update that leaves the school unchanged can retain an inactive legacy school. A school change clears friendships, pending requests and invitations, and invalidates affected poll options.

Recovery codes contain 128 random bits, are stored as SHA-256 hashes and rotate on use or password change. Treat the returned code as a credential; it cannot be retrieved again. Failed recovery does not disclose whether the account or code exists. Suspended accounts cannot log in or recover until an operator lifts the suspension.

Old consent versions trigger HTTP 428 for social/poll routes. Profile access, export, account deletion and logout remain available. The bundled client contains privacy text for version `2026-09-27`; publish corresponding client text when changing the server version.

## Friends and invitations

| Method | Path | Body/query | Response |
|---|---|---|---|
| GET | `/v1/people` | `q`, at least 2 characters | `people`, at most 30, same school, matching name/username substring |
| GET | `/v1/friends` | — | `friends`, incoming `requests`, outgoing `sent` |
| POST | `/v1/friends` | `userId` | Send request or accept incoming request |
| DELETE | `/v1/friends` | `userId` | Remove/reject/cancel connection |
| POST | `/v1/invites` | `{}` | `code`, `expires` (Unix seconds) |
| POST | `/v1/invites/accept` | `code` | Send request to inviter, or accept their existing request |

One invitation per account; creating another invalidates the previous one. Invites expire in seven days, work within one school, and respect blocks and suspension. Sharing a code does not bypass mutual friendship consent. The iOS app shares text/code; universal links and QR scanning are not implemented.

## Polls, inbox and points

| Method | Path | Body/query | Response |
|---|---|---|---|
| GET | `/v1/polls` | — | `polls`, `answered`, `total`, `day`, `skipped`, `minimumFriends`, `friendCount` |
| POST | `/v1/votes` | `pollId`, `selectedUserId`, `day` | `coinsEarned` |
| POST | `/v1/polls/skip` | `pollId`, `day` | `ok` |
| POST | `/v1/polls/shuffle` | `pollId`, `day` | `ok`; up to 3 changes per question/day |
| POST | `/v1/polls/restore` | `day` | `ok`; restore skipped questions for that day |
| GET | `/v1/inbox` | optional `q`, `cursor` | `flames` (up to 50), `nextCursor`, `unreadCount` |
| POST | `/v1/inbox/read` | received flame `id` | `ok` |
| GET | `/v1/ledger` | — | `entries`: latest 100 `id`, `amount`, `reason`, `timestamp` |

Polls contain `id`, `question`, `emoji`, `backgroundColor`, `options`. Options contain `id`, `userId`, `userName`. Four accepted, unsuspended friends are required. The server assigns 12 persistent daily questions from the versioned JSON content and snapshots the wording/options. Exposure counts over 30 days spread options across the full friend list. Changing options prioritizes friends absent from the previous set; some repeats are unavoidable with fewer than eight friends.

Always submit the `day` returned by the server (`YYYY-MM-DD` in UTC+09:00). A stale day is rejected with 409; refresh. A selected user must still be in the current offered options. Refresh after a conflict or uncertain network outcome: a lost response may have committed the vote. `BEGIN IMMEDIATE` plus unique `(responder,poll_id,day)` makes vote, 20-point reward and ledger insertion atomic. The server ignores client-supplied reward amounts. Skipping does not award points.

Flames contain only `id`, `pollQuestion`, `day`, `isRead`. Cursor values are opaque vote IDs scoped to the recipient; they do not encode precise timestamps. `nextCursor: null` ends pagination. `unreadCount` counts all visible unread compliments regardless of page or search filter. Block filtering happens before pagination. If maintenance removes the cursor's record, refresh the first page on 400. Question edits do not rewrite historical votes.

Deleting a recipient preserves the sender's answered-question count and ledger. Deleting a sender preserves delivered compliments with a null sender reference. Rows with neither participant are deleted. These semantics deliberately replace the original cascading vote deletion.

## Blocks and moderation

| Method | Path | Body/query | Response |
|---|---|---|---|
| GET | `/v1/blocks` | — | `people`: explicitly named blocks only |
| POST | `/v1/blocks` | `userId` | Block and remove relationship |
| DELETE | `/v1/blocks` | `userId` | Unblock; friendship is not restored |
| DELETE | `/v1/blocks/anonymous` | `{}` | Reset all anonymous sender blocks, including those whose reports expired |
| POST | `/v1/reports` | received flame `id`, `reason` (3–500 chars) | `ok`; report and anonymously block |
| GET | `/v1/reports` | — | latest 100 reports: `id`, `reason`, `timestamp`, `status`, `resolution` |
| POST | `/v1/reports/unblock` | own report `id` | `ok`; undo its anonymous sender block |

Report status: `open`, `closed`, `dismissed`, `action_taken`. Public responses never contain the subject's identity. Resolution messages are entered by the operator and must not disclose it. Administrative suspension, resolution and audit history are local CLI operations; there is no public admin endpoint. A minimum friend count does not prevent inference or fake accounts.

## Limits and deployment

Authentication attempts: 30 per connecting IP/10 minutes, plus 15 login/recovery attempts per username/10 minutes across IPs. Other requests: 600 per IP/minute. Counters survive worker/process restarts. This is a small-pilot control, not distributed abuse prevention.

Forwarded IPs are ignored unless `REMOTE_ADDR` is an exact member of `GAS_TRUSTED_PROXIES`. Only then is `X-Real-IP` accepted as one validated IP address. A trusted proxy **must overwrite this header**. Do not trust arbitrary client IP ranges. All operations use one local SQLite database; multi-host replication is not implemented.
