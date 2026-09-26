import json
import secrets
from datetime import date, timedelta
from common import MIN_FRIENDS, event, fail, field, timestamp, token_hash


class Polls:
    def invalidate_options(self, db, uid):
        # Remove deleted/changed IDs even from old offer snapshots; question text is retained.
        db.execute(
            "UPDATE offers SET options='[]' WHERE user_id=? OR EXISTS (SELECT 1 FROM json_each(offers.options) WHERE value=?)",
            (uid, uid),
        )

    def choose_options(self, db, uid, friends, day, pid, avoid=()):
        cutoff = (date.fromisoformat(day) - timedelta(days=30)).isoformat()
        counts = {
            r["target"]: r["total"]
            for r in db.execute(
                "SELECT target,SUM(count) total FROM exposures WHERE owner=? AND day>=? GROUP BY target",
                (uid, cutoff),
            )
        }
        ranked = sorted(
            friends,
            key=lambda f: (
                f["id"] in avoid,
                counts.get(f["id"], 0),
                token_hash(uid + day + pid + f["id"]),
            ),
        )
        ids = [f["id"] for f in ranked[:4]]
        for target in ids:
            db.execute(
                "INSERT INTO exposures VALUES (?,?,?,1) ON CONFLICT(owner,target,day) DO UPDATE SET count=count+1",
                (uid, target, day),
            )
        return ids

    def daily_offers(self, db, uid, day):
        friends = self.friends(db, uid)
        if len(friends) < MIN_FRIENDS:
            return []
        rows = db.execute(
            "SELECT * FROM offers WHERE user_id=? AND day=? ORDER BY position",
            (uid, day),
        ).fetchall()
        if not rows:
            offset = (
                date.fromisoformat(day).toordinal() * 12 + int(token_hash(uid)[:8], 16)
            ) % len(self.questions)
            selected = [
                self.questions[(offset + i) % len(self.questions)] for i in range(12)
            ]
            for position, q in enumerate(selected):
                options = self.choose_options(db, uid, friends, day, q["id"])
                db.execute(
                    "INSERT INTO offers (user_id,day,poll_id,question,emoji,color,options,position) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        uid,
                        day,
                        q["id"],
                        q["question"],
                        q["emoji"],
                        q["color"],
                        json.dumps(options),
                        position,
                    ),
                )
            rows = db.execute(
                "SELECT * FROM offers WHERE user_id=? AND day=? ORDER BY position",
                (uid, day),
            ).fetchall()
        allowed = {f["id"] for f in friends}
        answered = {
            r[0]
            for r in db.execute(
                "SELECT poll_id FROM votes WHERE responder=? AND day=?", (uid, day)
            )
        }
        for offer in rows:
            if offer["poll_id"] in answered:
                continue
            ids = json.loads(offer["options"])
            if len(ids) != 4 or not set(ids) <= allowed:
                ids = self.choose_options(db, uid, friends, day, offer["poll_id"])
                db.execute(
                    "UPDATE offers SET options=? WHERE user_id=? AND day=? AND poll_id=?",
                    (json.dumps(ids), uid, day, offer["poll_id"]),
                )
        return db.execute(
            "SELECT * FROM offers WHERE user_id=? AND day=? ORDER BY position",
            (uid, day),
        ).fetchall()

    def poll_result(self, db, uid, day):
        friends = self.friends(db, uid)
        names = {f["id"]: f["name"] for f in friends}
        rows = self.daily_offers(db, uid, day)
        answered = {
            r[0]
            for r in db.execute(
                "SELECT poll_id FROM votes WHERE responder=? AND day=?", (uid, day)
            )
        }
        polls = []
        for r in rows:
            if r["poll_id"] in answered or r["skipped"]:
                continue
            polls.append(
                dict(
                    id=r["poll_id"],
                    question=r["question"],
                    emoji=r["emoji"],
                    backgroundColor=r["color"],
                    options=[
                        dict(id=i, userId=i, userName=names[i])
                        for i in json.loads(r["options"])
                        if i in names
                    ],
                )
            )
        return dict(
            polls=polls,
            answered=len(answered),
            total=12,
            day=day,
            skipped=sum(r["skipped"] and r["poll_id"] not in answered for r in rows),
            minimumFriends=MIN_FRIENDS,
            friendCount=len(friends),
        )

    def poll_route(self, db, method, path, data, row, query):
        uid = row["id"]
        day = self.today()
        if path == "/v1/polls" and method == "GET":
            event(db, uid, "active")
            return self.poll_result(db, uid, day)
        if method == "POST" and path in (
            "/v1/votes",
            "/v1/polls/skip",
            "/v1/polls/shuffle",
            "/v1/polls/restore",
        ):
            if data.get("day") != day:
                fail(409, "A new day has started. Refresh your polls.")
            if path == "/v1/polls/restore":
                db.execute(
                    "UPDATE offers SET skipped=0 WHERE user_id=? AND day=?", (uid, day)
                )
                return {"ok": True}
            pid = field(data, "pollId")
            offers = self.daily_offers(db, uid, day)
            offer = next((o for o in offers if o["poll_id"] == pid), None)
            if not offer:
                fail(409, "Poll unavailable. You need at least four accepted friends.")
            if db.execute(
                "SELECT 1 FROM votes WHERE responder=? AND day=? AND poll_id=?",
                (uid, day, pid),
            ).fetchone():
                fail(409, "You have already answered this poll today")
            if path == "/v1/polls/skip":
                db.execute(
                    "UPDATE offers SET skipped=1 WHERE user_id=? AND day=? AND poll_id=?",
                    (uid, day, pid),
                )
                return {"ok": True}
            if path == "/v1/polls/shuffle":
                if offer["shuffles"] >= 3:
                    fail(
                        409, "You can change options three times per question each day"
                    )
                options = self.choose_options(
                    db,
                    uid,
                    self.friends(db, uid),
                    day,
                    pid,
                    json.loads(offer["options"]),
                )
                db.execute(
                    "UPDATE offers SET options=?,shuffles=shuffles+1 WHERE user_id=? AND day=? AND poll_id=?",
                    (json.dumps(options), uid, day, pid),
                )
                return {"ok": True}
            target = field(data, "selectedUserId")
            if target not in json.loads(offer["options"]):
                fail(
                    403,
                    "These options have changed. Refresh and choose an available friend.",
                )
            vote_id = secrets.token_hex(16)
            db.execute(
                "INSERT INTO votes VALUES (?,?,?,?,?,?,0,?)",
                (vote_id, uid, target, pid, day, timestamp(), offer["question"]),
            )
            db.execute("UPDATE users SET coins=coins+20 WHERE id=?", (uid,))
            db.execute(
                "INSERT INTO ledger VALUES (?,?,?,?,?,?)",
                (
                    secrets.token_hex(16),
                    uid,
                    20,
                    "Poll participation",
                    timestamp(),
                    vote_id,
                ),
            )
            event(db, uid, "voted")
            return {"coinsEarned": 20}
        if path == "/v1/inbox" and method == "GET":
            return self.inbox(db, uid, query)
        if path == "/v1/inbox/read" and method == "POST":
            vid = field(data, "id")
            result = db.execute(
                "UPDATE votes SET is_read=1 WHERE id=? AND recipient=?", (vid, uid)
            )
            if not result.rowcount:
                fail(404, "Compliment not found")
            return {"ok": True}
        return None

    def inbox(self, db, uid, query):
        term = query.get("q", [""])[0][:100]
        conditions = """recipient=? AND NOT EXISTS (SELECT 1 FROM blocks b WHERE
            (b.owner=? AND b.target=v.responder) OR (b.target=? AND b.owner=v.responder))"""
        args = [uid, uid, uid]
        unread = db.execute(
            "SELECT count(*) FROM votes v WHERE " + conditions + " AND is_read=0", args
        ).fetchone()[0]
        conditions += " AND instr(lower(question),lower(?))>0"
        args.append(term)
        cursor = query.get("cursor", [""])[0]
        if cursor:
            # Only an opaque vote ID leaves the server, never a precise vote timestamp.
            anchor = db.execute(
                "SELECT timestamp,id FROM votes WHERE id=? AND recipient=?",
                (cursor, uid),
            ).fetchone()
            if not anchor:
                fail(400, "Invalid inbox cursor; refresh the inbox")
            conditions += " AND (timestamp < ? OR (timestamp=? AND id<?))"
            args.extend([anchor["timestamp"], anchor["timestamp"], anchor["id"]])
        rows = db.execute(
            "SELECT * FROM votes v WHERE "
            + conditions
            + " ORDER BY timestamp DESC,id DESC LIMIT 51",
            args,
        ).fetchall()
        page = rows[:50]
        next_cursor = page[-1]["id"] if len(rows) > 50 else None
        return dict(
            flames=[
                dict(
                    id=v["id"],
                    pollQuestion=v["question"],
                    day=v["day"],
                    isRead=bool(v["is_read"]),
                )
                for v in page
            ],
            unreadCount=unread,
            nextCursor=next_cursor,
        )
