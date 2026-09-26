import secrets
import time
from common import event, fail, field, public_user, timestamp


class Social:
    def friends(self, db, uid):
        return db.execute(
            """SELECT u.* FROM users u JOIN friendships f
            ON (f.sender=? AND f.recipient=u.id) OR (f.recipient=? AND f.sender=u.id)
            WHERE f.accepted=1 AND u.suspended=0 ORDER BY u.username""",
            (uid, uid),
        ).fetchall()

    def blocked(self, db, a, b):
        return (
            db.execute(
                "SELECT 1 FROM blocks WHERE (owner=? AND target=?) OR (owner=? AND target=?)",
                (a, b, b, a),
            ).fetchone()
            is not None
        )

    def remove_friendship(self, db, a, b):
        db.execute(
            "DELETE FROM friendships WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?)",
            (a, b, b, a),
        )
        self.invalidate_options(db, a)
        self.invalidate_options(db, b)

    def request_friend(self, db, row, target):
        uid = row["id"]
        other = db.execute(
            "SELECT * FROM users WHERE id=? AND suspended=0", (target,)
        ).fetchone()
        if (
            not other
            or target == uid
            or other["school_id"] != row["school_id"]
            or self.blocked(db, uid, target)
        ):
            fail(404, "User unavailable")
        reverse = db.execute(
            "SELECT 1 FROM friendships WHERE sender=? AND recipient=?", (target, uid)
        ).fetchone()
        if reverse:
            db.execute(
                "UPDATE friendships SET accepted=1 WHERE sender=? AND recipient=?",
                (target, uid),
            )
            event(db, uid, "connected")
            event(db, target, "connected")
        else:
            db.execute(
                "INSERT OR IGNORE INTO friendships VALUES (?,?,0)", (uid, target)
            )
        return {"ok": True}

    def social_route(self, db, method, path, data, row, query):
        uid = row["id"]
        if path == "/v1/people" and method == "GET":
            term = query.get("q", [""])[0].strip().lower()[:100]
            if len(term) < 2:
                return {"people": []}
            rows = db.execute(
                """SELECT * FROM users u WHERE school_id=? AND id!=? AND suspended=0
                AND (instr(lower(username),?)>0 OR instr(lower(name),?)>0)
                AND NOT EXISTS (SELECT 1 FROM blocks b WHERE (b.owner=? AND b.target=u.id) OR (b.target=? AND b.owner=u.id))
                ORDER BY username LIMIT 30""",
                (row["school_id"], uid, term, term, uid, uid),
            )
            return {"people": [public_user(r) for r in rows]}
        if path == "/v1/friends" and method == "GET":
            requests = db.execute(
                "SELECT u.* FROM users u JOIN friendships f ON f.sender=u.id WHERE f.recipient=? AND f.accepted=0 AND u.suspended=0",
                (uid,),
            )
            sent = db.execute(
                "SELECT u.* FROM users u JOIN friendships f ON f.recipient=u.id WHERE f.sender=? AND f.accepted=0 AND u.suspended=0",
                (uid,),
            )
            return dict(
                friends=[public_user(r) for r in self.friends(db, uid)],
                requests=[public_user(r) for r in requests],
                sent=[public_user(r) for r in sent],
            )
        if path == "/v1/friends" and method == "POST":
            return self.request_friend(db, row, field(data, "userId"))
        if path == "/v1/friends" and method == "DELETE":
            self.remove_friendship(db, uid, field(data, "userId"))
            return {"ok": True}
        if path == "/v1/invites" and method == "POST":
            db.execute(
                "DELETE FROM invites WHERE owner=? OR expires<?", (uid, time.time())
            )
            code = secrets.token_urlsafe(18)
            expires = time.time() + 7 * 86400
            db.execute("INSERT INTO invites VALUES (?,?,?)", (code, uid, expires))
            return dict(code=code, expires=expires)
        if path == "/v1/invites/accept" and method == "POST":
            code = field(data, "code", 10, 80)
            invite = db.execute(
                "SELECT owner FROM invites WHERE code=? AND expires>?",
                (code, time.time()),
            ).fetchone()
            if not invite:
                fail(404, "Invitation has expired or is unavailable")
            # Knowing a code only sends a request; the inviter must still accept it.
            return self.request_friend(db, row, invite["owner"])
        if path == "/v1/blocks" and method == "GET":
            return {
                "people": [
                    public_user(p)
                    for p in db.execute(
                        "SELECT u.* FROM users u JOIN blocks b ON b.target=u.id WHERE b.owner=? AND b.hidden=0",
                        (uid,),
                    )
                ]
            }
        if path == "/v1/blocks/anonymous" and method == "DELETE":
            db.execute("DELETE FROM blocks WHERE owner=? AND hidden=1", (uid,))
            return {"ok": True}
        if path == "/v1/blocks" and method in ("POST", "DELETE"):
            target = field(data, "userId")
            if (
                not db.execute("SELECT 1 FROM users WHERE id=?", (target,)).fetchone()
                or target == uid
            ):
                fail(404, "User unavailable")
            if method == "POST":
                db.execute(
                    "INSERT OR IGNORE INTO blocks (owner,target) VALUES (?,?)",
                    (uid, target),
                )
                self.remove_friendship(db, uid, target)
            else:
                db.execute(
                    "DELETE FROM blocks WHERE owner=? AND target=?", (uid, target)
                )
            return {"ok": True}
        if path == "/v1/reports" and method == "GET":
            return {
                "reports": [
                    dict(r)
                    for r in db.execute(
                        "SELECT id,reason,timestamp,status,resolution FROM reports WHERE reporter=? ORDER BY timestamp DESC LIMIT 100",
                        (uid,),
                    )
                ]
            }
        if path == "/v1/reports" and method == "POST":
            vote = db.execute(
                "SELECT * FROM votes WHERE id=? AND recipient=?",
                (field(data, "id"), uid),
            ).fetchone()
            if not vote:
                fail(404, "Compliment not found")
            reason = field(data, "reason", 3, 500)
            db.execute(
                "INSERT OR IGNORE INTO reports (id,reporter,vote_id,reason,timestamp,subject_id) VALUES (?,?,?,?,?,?)",
                (
                    secrets.token_hex(16),
                    uid,
                    vote["id"],
                    reason,
                    timestamp(),
                    vote["responder"],
                ),
            )
            if vote["responder"]:
                db.execute(
                    "INSERT INTO blocks (owner,target,hidden) VALUES (?,?,1) ON CONFLICT(owner,target) DO UPDATE SET hidden=1",
                    (uid, vote["responder"]),
                )
                self.remove_friendship(db, uid, vote["responder"])
            return {"ok": True}
        if path == "/v1/reports/unblock" and method == "POST":
            report = db.execute(
                "SELECT subject_id FROM reports WHERE id=? AND reporter=?",
                (field(data, "id"), uid),
            ).fetchone()
            if not report:
                fail(404, "Report not found")
            db.execute(
                "DELETE FROM blocks WHERE owner=? AND target=? AND hidden=1",
                (uid, report["subject_id"]),
            )
            return {"ok": True}
        return None
