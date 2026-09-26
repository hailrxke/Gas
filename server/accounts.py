import hmac
import re
import secrets
import sqlite3
import time
from common import (
    CONSENT_VERSION,
    MIN_FRIENDS,
    birth_date,
    event,
    fail,
    field,
    own_user,
    password_field,
    password_hash,
    public_user,
    timestamp,
    token_hash,
    verify_password,
)
from storage import normalize


class Accounts:
    def session(self, db, uid, device="iPhone"):
        token = secrets.token_urlsafe(32)
        db.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
        db.execute(
            "INSERT INTO sessions (token,user_id,expires,id,created,device) VALUES (?,?,?,?,?,?)",
            (
                token_hash(token),
                uid,
                time.time() + 30 * 86400,
                secrets.token_hex(16),
                time.time(),
                device[:80],
            ),
        )
        return {"token": token}

    def rotate_recovery(self, db, uid):
        code = secrets.token_hex(16).upper()
        formatted = "-".join(code[i : i + 4] for i in range(0, len(code), 4))
        db.execute(
            "UPDATE users SET recovery_hash=? WHERE id=?", (token_hash(code), uid)
        )
        return formatted

    def school(self, db, sid):
        row = db.execute(
            "SELECT * FROM schools WHERE id=? AND active=1", (sid,)
        ).fetchone()
        if not row:
            fail(400, "Choose an available school from the catalog")
        return row

    def public_route(self, db, method, path, data, query):
        if method == "GET" and path == "/v1/config":
            return dict(consentVersion=CONSENT_VERSION, minimumFriends=MIN_FRIENDS)
        if method == "GET" and path == "/v1/schools":
            term = normalize(query.get("q", [""])[0][:100])
            rows = db.execute(
                """SELECT * FROM schools WHERE active=1 AND instr(search,?)>0
                ORDER BY region,name,id LIMIT 50""",
                (term,),
            )
            return {
                "schools": [
                    dict(
                        id=r["id"],
                        name=r["name"],
                        englishName=r["english_name"],
                        region=r["region"],
                        address=r["address"],
                        kind=r["kind"],
                    )
                    for r in rows
                ]
            }
        if method != "POST" or path not in ("/v1/register", "/v1/login", "/v1/recover"):
            return None
        username = field(data, "username", 3, 24).lower()
        if not re.fullmatch(r"[a-z0-9_]{3,24}", username):
            fail(400, "Username: use 3–24 letters, numbers or underscores")
        device = str(data.get("deviceName", "iPhone"))[:80]
        if path == "/v1/recover":
            code = (
                field(data, "recoveryCode", 32, 80)
                .replace("-", "")
                .replace(" ", "")
                .upper()
            )
            password = password_field(data, "newPassword")
            row = db.execute(
                "SELECT * FROM users WHERE username=?", (username,)
            ).fetchone()
            expected = (
                row["recovery_hash"]
                if row and row["recovery_hash"]
                else self.dummy_recovery
            )
            valid = hmac.compare_digest(expected, token_hash(code))
            if not row or not valid or row["suspended"]:
                fail(400, "Recovery details are invalid or unavailable")
            db.execute(
                "UPDATE users SET password=? WHERE id=?",
                (password_hash(password), row["id"]),
            )
            db.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
            return dict(
                self.session(db, row["id"], device),
                recoveryCode=self.rotate_recovery(db, row["id"]),
            )
        password = password_field(data)
        if path == "/v1/login":
            row = db.execute(
                "SELECT * FROM users WHERE username=?", (username,)
            ).fetchone()
            stored = row["password"] if row else self.dummy_hash
            valid = hmac.compare_digest(
                stored, password_hash(password, stored.split(":")[0])
            )
            if not row or not valid:
                fail(401, "Incorrect username or password")
            if row["suspended"]:
                fail(
                    403,
                    "This account has been suspended. Contact the service operator.",
                )
            event(db, row["id"], "active")
            return self.session(db, row["id"], device)
        if (
            data.get("consentVersion") != CONSENT_VERSION
            or data.get("consent") is not True
        ):
            fail(400, "Please read and accept the current privacy information")
        name = field(data, "name", 1, 40)
        school = self.school(db, field(data, "schoolId"))
        birth, age = birth_date(data)
        uid = secrets.token_hex(16)
        try:
            db.execute(
                """INSERT INTO users (id,username,name,password,school,school_id,age,birth_date,created_at,consent_version,consent_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    uid,
                    username,
                    name,
                    password_hash(password),
                    school["name"],
                    school["id"],
                    age,
                    birth,
                    timestamp(),
                    CONSENT_VERSION,
                    timestamp(),
                ),
            )
        except sqlite3.IntegrityError:
            fail(409, "Username is already taken")
        event(db, uid, "registered")
        event(db, uid, "active")
        return dict(
            self.session(db, uid, device), recoveryCode=self.rotate_recovery(db, uid)
        )

    def account_route(self, db, method, path, data, row, session):
        uid = row["id"]
        if path == "/v1/me" and method == "GET":
            return own_user(row)
        if path == "/v1/me" and method == "PATCH":
            name = field(data, "name", 1, 40)
            username = field(data, "username", 3, 24).lower()
            if not re.fullmatch(r"[a-z0-9_]{3,24}", username):
                fail(400, "Invalid username")
            sid = field(data, "schoolId")
            school = (
                db.execute("SELECT * FROM schools WHERE id=?", (sid,)).fetchone()
                if sid == row["school_id"]
                else self.school(db, sid)
            )
            if school["id"] != row["school_id"]:
                if data.get("confirmSchoolChange") is not True:
                    fail(
                        409,
                        "Changing schools removes your friendships and pending requests",
                    )
                verify_password(data, row)
                db.execute(
                    "DELETE FROM friendships WHERE sender=? OR recipient=?", (uid, uid)
                )
                self.invalidate_options(db, uid)
                db.execute("DELETE FROM invites WHERE owner=?", (uid,))
            try:
                db.execute(
                    "UPDATE users SET name=?,username=?,school=?,school_id=? WHERE id=?",
                    (name, username, school["name"], school["id"], uid),
                )
            except sqlite3.IntegrityError:
                fail(409, "Username is already taken")
            return {"ok": True}
        if path == "/v1/me" and method == "DELETE":
            verify_password(data, row)
            self.invalidate_options(db, uid)
            db.execute("DELETE FROM reports WHERE reporter=?", (uid,))
            db.execute("DELETE FROM audit WHERE target=?", (uid,))
            db.execute("DELETE FROM users WHERE id=?", (uid,))
            db.execute(
                "DELETE FROM votes WHERE responder IS NULL AND recipient IS NULL"
            )
            return {"ok": True}
        if path == "/v1/logout" and method == "POST":
            db.execute("DELETE FROM sessions WHERE id=?", (session["id"],))
            return {"ok": True}
        if path == "/v1/password" and method == "POST":
            verify_password(data, row)
            password = password_field(data, "newPassword")
            db.execute(
                "UPDATE users SET password=? WHERE id=?", (password_hash(password), uid)
            )
            db.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
            return dict(
                self.session(db, uid, str(data.get("deviceName", "iPhone"))),
                recoveryCode=self.rotate_recovery(db, uid),
            )
        if path == "/v1/recovery-code" and method == "POST":
            verify_password(data, row)
            return {"recoveryCode": self.rotate_recovery(db, uid)}
        if path == "/v1/sessions" and method == "GET":
            rows = db.execute(
                "SELECT * FROM sessions WHERE user_id=? AND expires>? ORDER BY created DESC",
                (uid, time.time()),
            )
            return {
                "sessions": [
                    dict(
                        id=s["id"],
                        device=s["device"],
                        created=s["created"],
                        expires=s["expires"],
                        current=s["id"] == session["id"],
                    )
                    for s in rows
                ]
            }
        if path == "/v1/sessions" and method == "DELETE":
            if data.get("allOthers") is True:
                db.execute(
                    "DELETE FROM sessions WHERE user_id=? AND id!=?",
                    (uid, session["id"]),
                )
            else:
                sid = field(data, "id")
                if sid == session["id"]:
                    fail(400, "Use Log Out for the current device")
                db.execute("DELETE FROM sessions WHERE user_id=? AND id=?", (uid, sid))
            return {"ok": True}
        if path == "/v1/export" and method == "POST":
            verify_password(data, row)
            # Never export the identity of someone who sent the requesting user an anonymous vote.
            sent = [
                dict(question=v["question"], day=v["day"])
                for v in db.execute(
                    "SELECT question,day FROM votes WHERE responder=?", (uid,)
                )
            ]
            ledger = [
                dict(v)
                for v in db.execute(
                    "SELECT amount,reason,timestamp FROM ledger WHERE user_id=?", (uid,)
                )
            ]
            reports = [
                dict(v)
                for v in db.execute(
                    "SELECT reason,status,resolution,timestamp FROM reports WHERE reporter=?",
                    (uid,),
                )
            ]
            return dict(
                profile=own_user(row),
                consent=dict(
                    version=row["consent_version"], acceptedAt=row["consent_at"]
                ),
                friends=[public_user(f) for f in self.friends(db, uid)],
                pendingConnections=self.social_route(
                    db, "GET", "/v1/friends", {}, row, {}
                ),
                namedBlocks=self.social_route(db, "GET", "/v1/blocks", {}, row, {})[
                    "people"
                ],
                anonymousBlockCount=db.execute(
                    "SELECT count(*) FROM blocks WHERE owner=? AND hidden=1", (uid,)
                ).fetchone()[0],
                sessions=self.account_route(
                    db, "GET", "/v1/sessions", {}, row, session
                )["sessions"],
                dailyActivity=[
                    dict(e)
                    for e in db.execute(
                        "SELECT event,day FROM events WHERE user_id=? ORDER BY day",
                        (uid,),
                    )
                ],
                sentVotes=sent,
                receivedVotes=[
                    dict(
                        question=v["question"], day=v["day"], isRead=bool(v["is_read"])
                    )
                    for v in db.execute(
                        "SELECT question,day,is_read FROM votes WHERE recipient=?",
                        (uid,),
                    )
                ],
                coinHistory=ledger,
                reports=reports,
            )
        if path == "/v1/ledger" and method == "GET":
            return {
                "entries": [
                    dict(v)
                    for v in db.execute(
                        "SELECT id,amount,reason,timestamp FROM ledger WHERE user_id=? ORDER BY timestamp DESC,id DESC LIMIT 100",
                        (uid,),
                    )
                ]
            }
        if path == "/v1/activity" and method == "POST":
            event(db, uid, "active")
            return {"ok": True}
        return None
