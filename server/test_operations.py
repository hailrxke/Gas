"""Regression tests for deployment, imports and privacy boundaries."""

import io
import json
import os
from contextlib import closing
from datetime import date
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from app import Application
from common import CONSENT_VERSION
from import_neis import fetch
from storage import import_schools, load_questions

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "  a secret with spaces  "


class OperationsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "gas.sqlite3"
        self.app = Application(self.path)
        with closing(self.app.connect()) as db, db:
            import_schools(db, [dict(id="school", name="Test School", region="Seoul")])

    def call(
        self, path, method="GET", body=None, token="", ip="127.0.0.1", forwarded=""
    ):
        raw = json.dumps(body or {}).encode()
        path, _, query = path.partition("?")
        env = dict(
            REQUEST_METHOD=method,
            PATH_INFO=path,
            QUERY_STRING=query,
            CONTENT_LENGTH=str(len(raw)),
            CONTENT_TYPE="application/json",
            HTTP_AUTHORIZATION="Bearer " + token,
            REMOTE_ADDR=ip,
            HTTP_X_REAL_IP=forwarded,
            **{"wsgi.input": io.BytesIO(raw)},
        )
        statuses = []
        result = b"".join(
            self.app(env, lambda s, h: statuses.append(int(s.split()[0])))
        )
        return statuses[0], json.loads(result)

    def register(self, username="student"):
        status, response = self.call(
            "/v1/register",
            "POST",
            dict(
                username=username,
                password=PASSWORD,
                name=username,
                schoolId="school",
                birthDate=f"{date.today().year - 16}-01-01",
                consent=True,
                consentVersion=CONSENT_VERSION,
            ),
        )
        self.assertEqual(status, 200, response)
        return response["token"], self.call("/v1/me", token=response["token"])[1]["id"]

    def manage(self, *args):
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "server/manage.py"),
                "--database",
                str(self.path),
                *args,
            ],
            capture_output=True,
            text=True,
        )

    def test_password_spaces_are_preserved(self):
        self.register()
        self.assertEqual(
            self.call(
                "/v1/login", "POST", dict(username="student", password=PASSWORD.strip())
            )[0],
            401,
        )
        self.assertEqual(
            self.call("/v1/login", "POST", dict(username="student", password=PASSWORD))[
                0
            ],
            200,
        )

    def test_school_import_invalid_batch_has_no_partial_writes(self):
        with closing(self.app.connect()) as db, db:
            for bad in (
                dict(id="bad", name=None, region="Seoul"),
                dict(id="new", name="Duplicate", region="Seoul"),
            ):
                with self.assertRaises(ValueError):
                    import_schools(
                        db, [dict(id="new", name="Valid School", region="Seoul"), bad]
                    )
                self.assertIsNone(
                    db.execute("SELECT id FROM schools WHERE id='new'").fetchone()
                )
            import_schools(db, [dict(id="school", name="Renamed", region="Seoul")])
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM schools").fetchone()[0], 1
            )

    def test_neis_pagination_and_source_ids(self):
        def row(number, kind="중학교"):
            return dict(
                ATPT_OFCDC_SC_CODE="B10",
                SD_SCHUL_CODE=str(number),
                SCHUL_NM="School",
                ENG_SCHUL_NM=None,
                LCTN_SC_NM="Seoul",
                ORG_RDNMA=None,
                SCHUL_KND_SC_NM=kind,
            )

        pages = [
            dict(
                schoolInfo=[
                    dict(head=[dict(list_total_count=1001)]),
                    dict(row=[row(1), row(2, "초등학교")]),
                ]
            ),
            dict(
                schoolInfo=[
                    dict(head=[dict(list_total_count=1001)]),
                    dict(row=[row(3)]),
                ]
            ),
        ]
        with patch(
            "import_neis.urlopen",
            side_effect=[io.BytesIO(json.dumps(p).encode()) for p in pages],
        ) as request:
            results = fetch("TEST-KEY")
            self.assertEqual(request.call_count, 2)
        self.assertEqual([r["id"] for r in results], ["neis:B10:1", "neis:B10:3"])
        with closing(self.app.connect()) as db, db:
            import_schools(db, results)
        self.assertNotIn("TEST-KEY", json.dumps(results))

    def test_question_catalog_rejects_duplicates(self):
        catalog = load_questions()
        catalog[1]["id"] = catalog[0]["id"]
        path = self.root / "questions.json"
        path.write_text(json.dumps(catalog))
        with self.assertRaises(ValueError):
            Application(self.path, questions_path=path)

    def test_untrusted_proxy_cannot_change_rate_limit_identity(self):
        for i in range(30):
            self.assertEqual(
                self.call("/v1/register", "POST", {}, forwarded=f"10.0.0.{i}")[0], 400
            )
        self.assertEqual(
            self.call("/v1/register", "POST", {}, forwarded="10.1.2.3")[0], 429
        )
        self.app.trusted_proxies = {"127.0.0.1"}
        self.assertEqual(
            self.call("/v1/register", "POST", {}, forwarded="10.1.2.3")[0], 400
        )
        # A trusted proxy must overwrite rather than append header values.
        self.assertEqual(
            self.call("/v1/register", "POST", {}, forwarded="10.1.2.3, 127.0.0.1")[0],
            400,
        )

    def test_consent_gate_keeps_export_and_deletion_available(self):
        token, uid = self.register()
        with closing(self.app.connect()) as db, db:
            db.execute("UPDATE users SET consent_version=NULL")
        self.assertEqual(self.call("/v1/friends", token=token)[0], 428)
        self.assertEqual(self.call("/v1/me", token=token)[0], 200)
        self.assertEqual(
            self.call("/v1/export", "POST", dict(password=PASSWORD), token)[0], 200
        )
        self.assertEqual(
            self.call(
                "/v1/consent",
                "POST",
                dict(consent=True, consentVersion=CONSENT_VERSION),
                token,
            )[0],
            200,
        )
        self.assertEqual(self.call("/v1/friends", token=token)[0], 200)
        with closing(self.app.connect()) as db, db:
            db.execute("UPDATE users SET consent_version=NULL")
        self.assertEqual(
            self.call("/v1/me", "DELETE", dict(password=PASSWORD), token)[0], 200
        )

    def test_moderation_resolution_does_not_expose_subject(self):
        a, aid = self.register()
        b, bid = self.register("recipient")
        with closing(self.app.connect()) as db, db:
            db.execute(
                "INSERT INTO votes VALUES (?,?,?,?,?,?,0,?)",
                (
                    "vote",
                    aid,
                    bid,
                    "p",
                    "2026-09-27",
                    "2026-09-27T12:34:56Z",
                    "A compliment",
                ),
            )
        self.call("/v1/reports", "POST", dict(id="vote", reason="Unwanted"), b)
        rid = self.call("/v1/reports", token=b)[1]["reports"][0]["id"]
        result = self.manage(
            "resolve",
            rid,
            "--status",
            "action_taken",
            "--message",
            "Reviewed by the service operator",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = self.call("/v1/reports", token=b)[1]["reports"][0]
        self.assertEqual(report["status"], "action_taken")
        self.assertNotIn(aid, json.dumps(report))
        self.assertEqual(self.call("/v1/inbox", token=b)[1]["flames"], [])
        self.call("/v1/blocks/anonymous", "DELETE", {}, b)
        self.assertEqual(len(self.call("/v1/inbox", token=b)[1]["flames"]), 1)

    def test_private_cursor_and_block_filter_before_pagination(self):
        a, aid = self.register()
        b, bid = self.register("recipient")
        c, cid = self.register("third")
        with closing(self.app.connect()) as db, db:
            for i in range(70):
                db.execute(
                    "INSERT INTO votes VALUES (?,?,?,?,?,?,0,?)",
                    (
                        f"{i:032x}",
                        aid,
                        bid,
                        str(i),
                        "2026-09-27",
                        "2026-09-27T12:34:56Z",
                        "A compliment",
                    ),
                )
            db.execute(
                "INSERT INTO votes VALUES (?,?,?,?,?,?,0,?)",
                (
                    "older",
                    cid,
                    bid,
                    "old",
                    "2026-09-26",
                    "2026-09-26T00:00:00Z",
                    "Older compliment",
                ),
            )
        first = self.call("/v1/inbox", token=b)[1]
        self.assertEqual(len(first["nextCursor"]), 32)
        self.assertNotIn("12:34:56", json.dumps(first))
        self.assertEqual(
            self.call("/v1/inbox?cursor=" + first["nextCursor"], token=c)[0], 400
        )
        self.call("/v1/blocks", "POST", dict(userId=aid), b)
        inbox = self.call("/v1/inbox", token=b)[1]
        self.assertEqual([v["id"] for v in inbox["flames"]], ["older"])
        self.assertEqual(inbox["unreadCount"], 1)

    def test_backup_restore_prune_and_rotation(self):
        token, uid = self.register()
        with closing(self.app.connect()) as db, db:
            db.execute(
                "INSERT INTO votes VALUES (?,?,?,?,?,?,0,?)",
                (
                    "old",
                    uid,
                    uid,
                    "old",
                    "2000-01-01",
                    "2000-01-01T00:00:00Z",
                    "Old compliment",
                ),
            )
        backups = self.root / "backups"
        backups.mkdir()
        expired = backups / "gas-backup-20000101T000000000000Z.sqlite3"
        expired.write_text("old")
        unrelated = backups / "manual.sqlite3"
        unrelated.write_text("keep")
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/maintenance.py"),
                "--database",
                str(self.path),
                "--backups",
                str(backups),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(expired.exists())
        self.assertTrue(unrelated.exists())
        snapshot = next(backups.glob("gas-backup-*.sqlite3"))
        with closing(sqlite3.connect(snapshot)) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("SELECT count(*) FROM votes").fetchone()[0], 1)
        self.assertEqual(self.call("/v1/inbox", token=token)[1]["flames"], [])
        restored = Application(snapshot)
        with closing(restored.connect()) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM users").fetchone()[0], 1)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertNotEqual(self.manage("backup", str(snapshot)).returncode, 0)
        if os.name == "posix":
            self.assertEqual(snapshot.stat().st_mode & 0o777, 0o600)

    def test_newer_schema_is_never_downgraded(self):
        with closing(self.app.connect()) as db, db:
            db.execute("PRAGMA user_version=999")
        with self.assertRaises(RuntimeError):
            Application(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 999)


if __name__ == "__main__":
    unittest.main()
