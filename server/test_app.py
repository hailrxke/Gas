import io
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from unittest.mock import patch
from app import Application
from common import CONSENT_VERSION, age_on, password_hash
from storage import import_schools

PASSWORD = "correct horse battery"
BIRTH = f"{date.today().year - 16}-01-01"


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.sqlite3"
        self.app = Application(self.db)
        self.recovery = {}
        self.number = 0
        with closing(self.app.connect()) as db, db:
            import_schools(
                db,
                [
                    dict(id="a", name="Same School", region="Seoul"),
                    dict(id="b", name="Same School", region="Busan"),
                ],
            )

    def call(self, path, method="GET", body=None, token="", ip="127.0.0.1"):
        raw = json.dumps(body).encode() if body is not None else b""
        route, _, query = path.partition("?")
        env = dict(
            REQUEST_METHOD=method,
            PATH_INFO=route,
            QUERY_STRING=query,
            CONTENT_LENGTH=str(len(raw)),
            CONTENT_TYPE="application/json",
            HTTP_AUTHORIZATION="Bearer " + token,
            REMOTE_ADDR=ip,
            **{"wsgi.input": io.BytesIO(raw)},
        )
        statuses = []
        payload = b"".join(
            self.app(env, lambda s, h: statuses.append(int(s.split()[0])))
        )
        return statuses[0], json.loads(payload)

    def registration(self, name="alice", school="a"):
        return dict(
            username=name,
            password=PASSWORD,
            name=name,
            schoolId=school,
            birthDate=BIRTH,
            consent=True,
            consentVersion=CONSENT_VERSION,
        )

    def register(self, name, school="a"):
        status, response = self.call(
            "/v1/register", "POST", self.registration(name, school)
        )
        self.assertEqual(status, 200, response)
        token = response["token"]
        self.recovery[name] = response["recoveryCode"]
        status, user = self.call("/v1/me", token=token)
        self.assertEqual(status, 200, user)
        return token, user["id"]

    def connect(self, a, aid, b, bid):
        self.assertEqual(self.call("/v1/friends", "POST", {"userId": bid}, a)[0], 200)
        self.assertEqual(self.call("/v1/friends", "POST", {"userId": aid}, b)[0], 200)

    def ready(self, count=4):
        a, aid = self.register("alice")
        friends = []
        for i in range(count):
            b, bid = self.register(f"friend_{i:02}")
            self.connect(a, aid, b, bid)
            friends.append((b, bid))
        return (a, aid), friends

    def vote(self, a, poll=None):
        response = self.call("/v1/polls", token=a)[1]
        poll = poll or response["polls"][0]
        return self.call(
            "/v1/votes",
            "POST",
            dict(
                pollId=poll["id"],
                selectedUserId=poll["options"][0]["userId"],
                day=response["day"],
            ),
            a,
        )

    def test_registration_login_and_hashes(self):
        a, aid = self.register("alice")
        with closing(self.app.connect()) as db, db:
            user = db.execute("SELECT * FROM users").fetchone()
            self.assertNotIn(PASSWORD, user["password"])
            self.assertNotEqual(
                a, db.execute("SELECT token FROM sessions").fetchone()[0]
            )
            self.assertNotIn(self.recovery["alice"], user["recovery_hash"])
            self.assertEqual(user["consent_version"], CONSENT_VERSION)
        self.assertEqual(
            self.call(
                "/v1/login",
                "POST",
                dict(username="alice", password="incorrect password"),
            )[0],
            401,
        )
        result = self.call(
            "/v1/login", "POST", dict(username="ALICE", password=PASSWORD)
        )[1]
        self.assertEqual(self.call("/v1/me", token=result["token"])[0], 200)
        self.call("/v1/logout", "POST", {}, a)
        self.assertEqual(self.call("/v1/me", token=a)[0], 401)

    def test_school_catalog_and_consent(self):
        schools = self.call("/v1/schools?q=same")[1]["schools"]
        self.assertEqual({s["id"] for s in schools}, {"a", "b"})
        for change in [
            dict(schoolId="missing"),
            dict(consent=False),
            dict(consentVersion="old"),
            dict(birthDate="2099-01-01"),
            dict(birthDate="invalid"),
            dict(username="x"),
        ]:
            self.assertEqual(
                self.call("/v1/register", "POST", dict(self.registration(), **change))[
                    0
                ],
                400,
            )
        self.register("alice")
        self.assertEqual(self.call("/v1/register", "POST", self.registration())[0], 409)

    def test_age_is_computed_from_birth_date(self):
        self.assertEqual(age_on("2010-09-28", date(2026, 9, 27)), 15)
        self.assertEqual(age_on("2010-09-28", date(2026, 9, 28)), 16)

    def test_search_same_name_different_school(self):
        a, aid = self.register("alice")
        b, bid = self.register("bobby")
        c, cid = self.register("carol", "b")
        self.assertEqual(
            self.call("/v1/people?q=bob", token=a)[1]["people"][0]["id"], bid
        )
        self.assertEqual(self.call("/v1/people?q=car", token=a)[1]["people"], [])
        self.assertEqual(self.call("/v1/friends", "POST", dict(userId=cid), a)[0], 404)
        self.call("/v1/friends", "POST", dict(userId=bid), a)
        self.assertEqual(self.call("/v1/friends", token=a)[1]["friends"], [])
        self.assertEqual(self.call("/v1/friends", token=b)[1]["requests"][0]["id"], aid)

    def test_four_friends_required(self):
        (a, aid), friends = self.ready(3)
        self.assertEqual(self.call("/v1/polls", token=a)[1]["polls"], [])
        d, did = self.register("fourth")
        self.connect(a, aid, d, did)
        self.assertEqual(len(self.call("/v1/polls", token=a)[1]["polls"]), 12)

    def test_fair_options_beyond_first_fifteen(self):
        (a, aid), friends = self.ready(20)
        polls = self.call("/v1/polls", token=a)[1]["polls"]
        counts = Counter(o["userId"] for p in polls for o in p["options"])
        self.assertEqual(set(counts), {f[1] for f in friends})
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)
        self.assertEqual(polls, self.call("/v1/polls", token=a)[1]["polls"])

    def test_atomic_vote_and_ledger(self):
        (a, aid), friends = self.ready()
        state = self.call("/v1/polls", token=a)[1]
        p = state["polls"][0]
        body = dict(
            pollId=p["id"], selectedUserId=p["options"][0]["userId"], day=state["day"]
        )
        with ThreadPoolExecutor(max_workers=4) as pool:
            codes = list(
                pool.map(lambda _: self.call("/v1/votes", "POST", body, a)[0], range(4))
            )
        self.assertEqual(sorted(codes), [200, 409, 409, 409])
        self.assertEqual(self.call("/v1/me", token=a)[1]["coins"], 20)
        self.assertEqual(len(self.call("/v1/ledger", token=a)[1]["entries"]), 1)

    def test_vote_invalid_target_and_stale_day(self):
        (a, aid), friends = self.ready()
        state = self.call("/v1/polls", token=a)[1]
        p = state["polls"][0]
        self.assertEqual(
            self.call(
                "/v1/votes",
                "POST",
                dict(pollId=p["id"], selectedUserId=aid, day=state["day"]),
                a,
            )[0],
            403,
        )
        self.assertEqual(
            self.call(
                "/v1/votes",
                "POST",
                dict(
                    pollId=p["id"],
                    selectedUserId=p["options"][0]["userId"],
                    day="2000-01-01",
                ),
                a,
            )[0],
            409,
        )

    def test_daily_rotation_and_snapshot(self):
        (a, aid), friends = self.ready()
        with patch.object(self.app, "today", return_value="2026-09-27"):
            first = self.call("/v1/polls", token=a)[1]["polls"]
        with patch.object(self.app, "today", return_value="2026-09-28"):
            second = self.call("/v1/polls", token=a)[1]["polls"]
        self.assertFalse({p["id"] for p in first} & {p["id"] for p in second})
        before = self.call("/v1/polls", token=a)[1]["polls"]
        target = before[0]["options"][0]["userId"]
        self.vote(a, before[0])
        token = next(t for t, i in friends if i == target)
        question = self.call("/v1/inbox", token=token)[1]["flames"][0]["pollQuestion"]
        self.app.questions = []
        self.assertEqual(
            self.call("/v1/inbox", token=token)[1]["flames"][0]["pollQuestion"],
            question,
        )
        self.assertEqual(len(self.call("/v1/polls", token=a)[1]["polls"]), 11)

    def test_skip_restore_and_shuffle(self):
        (a, aid), friends = self.ready(8)
        state = self.call("/v1/polls", token=a)[1]
        p = state["polls"][0]
        body = dict(pollId=p["id"], day=state["day"])
        self.call("/v1/polls/skip", "POST", body, a)
        self.assertNotIn(
            p["id"], [p["id"] for p in self.call("/v1/polls", token=a)[1]["polls"]]
        )
        self.app = Application(self.db)
        self.assertEqual(self.call("/v1/polls", token=a)[1]["skipped"], 1)
        self.call("/v1/polls/restore", "POST", dict(day=state["day"]), a)
        self.call("/v1/polls/shuffle", "POST", body, a)
        changed = self.call("/v1/polls", token=a)[1]["polls"][0]
        self.assertFalse(
            {o["userId"] for o in p["options"]}
            & {o["userId"] for o in changed["options"]}
        )
        self.call("/v1/polls/shuffle", "POST", body, a)
        self.call("/v1/polls/shuffle", "POST", body, a)
        self.assertEqual(self.call("/v1/polls/shuffle", "POST", body, a)[0], 409)

    def test_recovery_is_single_use_and_revokes_sessions(self):
        a, aid = self.register("alice")
        code = self.recovery["alice"]
        self.assertEqual(
            self.call(
                "/v1/recover",
                "POST",
                dict(
                    username="alice",
                    recoveryCode="A" * 32,
                    newPassword="new secure password",
                ),
            )[0],
            400,
        )
        body = dict(
            username="alice", recoveryCode=code, newPassword="new secure password"
        )
        status, response = self.call("/v1/recover", "POST", body)
        self.assertEqual(status, 200, response)
        self.assertNotEqual(code, response["recoveryCode"])
        self.assertEqual(self.call("/v1/me", token=a)[0], 401)
        self.assertEqual(self.call("/v1/recover", "POST", body)[0], 400)
        self.assertEqual(self.call("/v1/me", token=response["token"])[0], 200)

    def test_change_password_and_session_revocation(self):
        a, aid = self.register("alice")
        b = self.call(
            "/v1/login",
            "POST",
            dict(username="alice", password=PASSWORD, deviceName="Second phone"),
        )[1]["token"]
        sessions = self.call("/v1/sessions", token=a)[1]["sessions"]
        self.assertEqual(len(sessions), 2)
        self.assertNotIn("token", json.dumps(sessions))
        self.call("/v1/sessions", "DELETE", dict(allOthers=True), a)
        self.assertEqual(self.call("/v1/me", token=b)[0], 401)
        status, result = self.call(
            "/v1/password",
            "POST",
            dict(password=PASSWORD, newPassword="brand new password"),
            a,
        )
        self.assertEqual(status, 200)
        self.assertEqual(self.call("/v1/me", token=a)[0], 401)
        self.assertEqual(self.call("/v1/me", token=result["token"])[0], 200)

    def test_edit_profile_school_change_requires_confirmation(self):
        a, aid = self.register("alice")
        b, bid = self.register("bobby")
        self.connect(a, aid, b, bid)
        body = dict(name="Alice Example", username="alice_new", schoolId="b")
        self.assertEqual(self.call("/v1/me", "PATCH", body, a)[0], 409)
        self.assertEqual(
            self.call(
                "/v1/me",
                "PATCH",
                dict(body, confirmSchoolChange=True, password=PASSWORD),
                a,
            )[0],
            200,
        )
        self.assertEqual(self.call("/v1/friends", token=b)[1]["friends"], [])
        self.assertEqual(self.call("/v1/me", token=a)[1]["schoolId"], "b")

    def test_invitation_still_requires_consent(self):
        a, aid = self.register("alice")
        b, bid = self.register("bobby")
        code = self.call("/v1/invites", "POST", {}, a)[1]["code"]
        self.assertEqual(
            self.call("/v1/invites/accept", "POST", dict(code=code), b)[0], 200
        )
        self.assertEqual(self.call("/v1/friends", token=a)[1]["friends"], [])
        self.call("/v1/friends", "POST", dict(userId=bid), a)
        self.assertEqual(len(self.call("/v1/friends", token=a)[1]["friends"]), 1)
        self.call("/v1/invites", "POST", {}, a)
        self.assertEqual(
            self.call("/v1/invites/accept", "POST", dict(code=code), b)[0], 404
        )

    def test_report_privacy_resolution_and_anonymous_unblock(self):
        (a, aid), friends = self.ready()
        p = self.call("/v1/polls", token=a)[1]["polls"][0]
        self.vote(a, p)
        b = next(t for t, i in friends if i == p["options"][0]["userId"])
        flame = self.call("/v1/inbox", token=b)[1]["flames"][0]
        self.assertEqual(set(flame), {"id", "pollQuestion", "day", "isRead"})
        self.assertEqual(
            self.call(
                "/v1/reports", "POST", dict(id=flame["id"], reason="Unwanted"), a
            )[0],
            404,
        )
        self.call("/v1/reports", "POST", dict(id=flame["id"], reason="Unwanted"), b)
        self.assertEqual(self.call("/v1/blocks", token=b)[1]["people"], [])
        reports = self.call("/v1/reports", token=b)[1]["reports"]
        self.assertNotIn(aid, json.dumps(reports))
        rid = reports[0]["id"]
        with closing(self.app.connect()) as db, db:
            db.execute(
                "UPDATE reports SET status='closed',resolution='Reviewed' WHERE id=?",
                (rid,),
            )
        self.assertEqual(
            self.call("/v1/reports", token=b)[1]["reports"][0]["resolution"], "Reviewed"
        )
        self.call("/v1/reports/unblock", "POST", dict(id=rid), b)
        self.assertEqual(len(self.call("/v1/inbox", token=b)[1]["flames"]), 1)

    def test_deletion_preserves_anonymous_history_and_daily_limit(self):
        (a, aid), friends = self.ready(5)
        p = self.call("/v1/polls", token=a)[1]["polls"][0]
        target = p["options"][0]["userId"]
        b = next(t for t, i in friends if i == target)
        self.vote(a, p)
        self.call("/v1/me", "DELETE", dict(password=PASSWORD), b)
        self.assertEqual(self.call("/v1/polls", token=a)[1]["answered"], 1)
        self.assertEqual(self.call("/v1/me", token=a)[1]["coins"], 20)
        self.assertEqual(len(self.call("/v1/ledger", token=a)[1]["entries"]), 1)
        p = self.call("/v1/polls", token=a)[1]["polls"][0]
        b = next(t for t, i in friends if i == p["options"][0]["userId"])
        self.vote(a, p)
        self.call("/v1/me", "DELETE", dict(password=PASSWORD), a)
        self.assertEqual(len(self.call("/v1/inbox", token=b)[1]["flames"]), 1)
        with closing(self.app.connect()) as db, db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM sessions WHERE user_id=?", (aid,)
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM ledger WHERE user_id=?", (aid,)
                ).fetchone()[0],
                0,
            )

    def test_export_excludes_anonymous_sender(self):
        (a, aid), friends = self.ready()
        p = self.call("/v1/polls", token=a)[1]["polls"][0]
        self.vote(a, p)
        b = next(t for t, i in friends if i == p["options"][0]["userId"])
        self.assertEqual(
            self.call("/v1/export", "POST", dict(password="wrong password"), b)[0], 403
        )
        exported = self.call("/v1/export", "POST", dict(password=PASSWORD), b)[1]
        self.assertNotIn("responder", json.dumps(exported))
        self.assertNotIn("recovery_hash", json.dumps(exported))
        self.assertEqual(exported["sentVotes"], [])

    def test_inbox_cursor_and_unread_total(self):
        a, aid = self.register("alice")
        b, bid = self.register("bobby")
        with closing(self.app.connect()) as db, db:
            for i in range(125):
                db.execute(
                    "INSERT INTO votes VALUES (?,?,?,?,?,?,0,?)",
                    (
                        f"{i:032}",
                        aid,
                        bid,
                        str(i),
                        "2026-09-27",
                        "2026-09-27T00:00:00Z",
                        "A compliment",
                    ),
                )
        first = self.call("/v1/inbox", token=b)[1]
        self.assertEqual(len(first["flames"]), 50)
        self.assertEqual(first["unreadCount"], 125)
        second = self.call("/v1/inbox?cursor=" + first["nextCursor"], token=b)[1]
        third = self.call("/v1/inbox?cursor=" + second["nextCursor"], token=b)[1]
        self.assertEqual(
            len({f["id"] for page in (first, second, third) for f in page["flames"]}),
            125,
        )
        self.assertIsNone(third["nextCursor"])
        self.assertEqual(self.call("/v1/inbox?cursor=bad", token=b)[0], 400)

    def test_suspension_blocks_login_and_recovery(self):
        a, aid = self.register("alice")
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("manage.py")),
                "--database",
                str(self.db),
                "suspend",
                aid,
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.call("/v1/me", token=a)[0], 401)
        self.assertEqual(
            self.call("/v1/login", "POST", dict(username="alice", password=PASSWORD))[
                0
            ],
            403,
        )
        self.assertEqual(
            self.call(
                "/v1/recover",
                "POST",
                dict(
                    username="alice",
                    recoveryCode=self.recovery["alice"],
                    newPassword="new password!",
                ),
            )[0],
            400,
        )

    def test_rate_limit_failed_attempts_and_proxy_boundary(self):
        for _ in range(15):
            self.assertEqual(
                self.call(
                    "/v1/login", "POST", dict(username="missing", password=PASSWORD)
                )[0],
                401,
            )
        self.assertEqual(
            self.call(
                "/v1/login",
                "POST",
                dict(username="missing", password=PASSWORD),
                ip="other",
            )[0],
            429,
        )

    def test_restart_and_expiry(self):
        a, aid = self.register("alice")
        self.app = Application(self.db)
        self.assertEqual(self.call("/v1/me", token=a)[1]["id"], aid)
        with closing(self.app.connect()) as db, db:
            db.execute("UPDATE sessions SET expires=0")
        self.assertEqual(self.call("/v1/me", token=a)[0], 401)

    def test_request_validation(self):
        self.assertEqual(self.call("/v1/register", "POST", [])[0], 400)
        self.assertEqual(self.call("/v1/me")[0], 401)
        self.assertEqual(self.call("/health")[1]["schemaVersion"], 2)
        for size, body, ct, expected in [
            ("16385", b"", "application/json", 413),
            ("1", b"{", "application/json", 400),
            ("2", b"{}", "text/plain", 415),
        ]:
            statuses = []
            env = dict(
                REQUEST_METHOD="POST",
                PATH_INFO="/v1/register",
                CONTENT_LENGTH=size,
                CONTENT_TYPE=ct,
                **{"wsgi.input": io.BytesIO(body)},
            )
            list(self.app(env, lambda s, h: statuses.append(int(s.split()[0]))))
            self.assertEqual(statuses[0], expected)

    def test_legacy_migration_preserves_data_and_backs_up(self):
        old = Path(self.temp.name) / "legacy.sqlite3"
        db = sqlite3.connect(old)
        db.executescript(Path(__file__).with_name("legacy_schema.sql").read_text())
        db.execute(
            "INSERT INTO users VALUES (?,?,?,?,?,?,?)",
            ("u", "legacy", "Legacy", password_hash(PASSWORD), "Old School", 16, 20),
        )
        db.execute(
            "INSERT INTO votes VALUES (?,?,?,?,?,?,?)",
            ("v", "u", "u", "1", "2026-09-26", "2026-09-26T00:00:00Z", 0),
        )
        db.execute(
            "INSERT INTO reports VALUES (?,?,?,?,?)",
            ("r", "u", "v", "A report", "2026-09-26T00:00:00Z"),
        )
        db.commit()
        db.close()
        migrated = Application(old)
        Application(old)
        self.assertTrue(Path(str(old) + ".pre-v2.bak").exists())
        with closing(migrated.connect()) as db, db:
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(db.execute("SELECT coins FROM users").fetchone()[0], 20)
            self.assertEqual(db.execute("SELECT amount FROM ledger").fetchone()[0], 20)
            self.assertTrue(db.execute("SELECT question FROM votes").fetchone()[0])
            self.assertEqual(
                db.execute("SELECT subject_id FROM reports").fetchone()[0], "u"
            )
            self.assertTrue(
                db.execute("SELECT school_id FROM users")
                .fetchone()[0]
                .startswith("legacy-")
            )


if __name__ == "__main__":
    unittest.main()
