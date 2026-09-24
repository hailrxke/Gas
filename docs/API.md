# API contract

JSON request/response bodies. Authenticated routes require `Authorization: Bearer <token>`. Error responses contain `{"error":"message"}`. Max request size: 16 KiB. Tokens expire after 30 days and are revoked at logout or account deletion. API URLs are rooted at `/v1`.

| Method | Path | Body or query | Response |
|---|---|---|---|
| GET | `/health` | none | `status` |
| POST | `/v1/register` | `username`, `password`, `name`, `school`, integer `age` | `token` |
| POST | `/v1/login` | `username`, `password` | `token` |
| POST | `/v1/logout` | `{}` | `ok` |
| GET | `/v1/me` | none | `id`, `username`, `name`, `school`, `age`, `coins` |
| DELETE | `/v1/me` | `password` | `ok` |
| GET | `/v1/schools` | optional `q` | `schools`: self-reported names, max 30 |
| GET | `/v1/people` | `q`: exact username | `people`: public profiles in same school |
| GET | `/v1/friends` | none | `friends`, incoming `requests`, outgoing `sent` |
| POST | `/v1/friends` | `userId` | Send a request, or accept an existing incoming request |
| DELETE | `/v1/friends` | `userId` | Remove friendship, reject or cancel request |
| GET | `/v1/polls` | none | unanswered `polls`, `answered`, `total` |
| POST | `/v1/votes` | `pollId`, `selectedUserId` | `coinsEarned` |
| GET | `/v1/inbox` | none | `flames`: latest 200, newest first |
| POST | `/v1/inbox/read` | `id`: received flame ID | `ok` |
| GET | `/v1/blocks` | none | `people`: explicitly blocked profiles only |
| POST | `/v1/blocks` | `userId` | Block and remove relationship |
| DELETE | `/v1/blocks` | `userId` | Unblock; friendship is not restored |
| POST | `/v1/reports` | `id`: received flame ID, `reason` | Record report and anonymously block sender |

Public profiles contain `id`, `username`, `name`, `school`. They do not include age, coins or credentials.

Polls contain `id`, `question`, `emoji`, `backgroundColor`, `options`. Each option contains `id`, `userId`, `userName`. At most four accepted friends are offered; one accepted friend is sufficient to start. A vote is accepted only for a currently offered option. Clients must refresh after a 409 response or uncertain network outcome instead of assuming the write failed.

Flames contain only `id`, `pollQuestion`, `day` (`YYYY-MM-DD`, Korean day) and `isRead`. Vote responder identities are never returned in the inbox or report response. Anonymous report blocks are deliberately omitted from the named block list.

Usernames are case-insensitive ASCII letters, digits or underscores, 3–24 characters. Passwords are 10–128 characters. School names are whitespace-normalized and otherwise compared exactly. Auth attempts are limited per connecting IP. The server ignores forwarded IP headers; configure deployment accordingly.

SQLite `BEGIN IMMEDIATE` transactions plus a unique `(responder, poll_id, day)` constraint serialize competing votes. The server awards a fixed 20 coins, never a client-supplied amount. New daily rounds start at 00:00 UTC+09:00.
