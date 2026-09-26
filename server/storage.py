"""Versioned, transactional SQLite migration from the original MVP database."""

import hashlib
import json
import os
import sqlite3
import unicodedata
from pathlib import Path

VERSION = 2


def normalize(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def initialize(path, questions):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version > VERSION:
            raise RuntimeError(
                "Database is newer than this server. Refusing to downgrade."
            )
        if version == VERSION:
            return
        existed = (
            db.execute("SELECT 1 FROM sqlite_master WHERE name='users'").fetchone()
            is not None
        )
        if existed:
            backup = path.with_name(path.name + ".pre-v2.bak")
            # Never overwrite the first pre-migration backup.
            if not backup.exists():
                fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.close(fd)
                destination = sqlite3.connect(backup)
                try:
                    db.backup(destination)
                    if (
                        destination.execute("PRAGMA integrity_check").fetchone()[0]
                        != "ok"
                    ):
                        raise RuntimeError(
                            "Pre-migration backup failed integrity check"
                        )
                except Exception:
                    destination.close()
                    backup.unlink(missing_ok=True)
                    raise
                finally:
                    destination.close()
        else:
            db.executescript(Path(__file__).with_name("legacy_schema.sql").read_text())
        db.execute("PRAGMA foreign_keys=OFF")
        db.execute("BEGIN IMMEDIATE")
        db.execute("""CREATE TABLE schools (id TEXT PRIMARY KEY, name TEXT NOT NULL, english_name TEXT NOT NULL DEFAULT '',
            region TEXT NOT NULL, address TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL DEFAULT '',
            search TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, source TEXT NOT NULL DEFAULT 'operator')""")
        for col in [
            "school_id TEXT REFERENCES schools(id)",
            "birth_date TEXT",
            "recovery_hash TEXT",
            "suspended INTEGER NOT NULL DEFAULT 0",
            "created_at TEXT NOT NULL DEFAULT ''",
            "consent_version TEXT",
            "consent_at TEXT",
        ]:
            db.execute("ALTER TABLE users ADD COLUMN " + col)
        # Preserve legacy school groups, but do not expose unverified legacy names for new sign-ups.
        for row in db.execute("SELECT DISTINCT school FROM users").fetchall():
            name = row["school"]
            sid = "legacy-" + hashlib.sha256(normalize(name).encode()).hexdigest()[:24]
            db.execute(
                "INSERT OR IGNORE INTO schools (id,name,region,search,active,source) VALUES (?,?,?,?,0,?)",
                (sid, name, "Unknown", normalize(name), "legacy"),
            )
            db.execute("UPDATE users SET school_id=? WHERE school=?", (sid, name))
        for col in [
            "id TEXT",
            "created REAL NOT NULL DEFAULT 0",
            "device TEXT NOT NULL DEFAULT 'Legacy device'",
        ]:
            db.execute("ALTER TABLE sessions ADD COLUMN " + col)
        db.execute("UPDATE sessions SET id=lower(hex(randomblob(16)))")
        db.execute("CREATE UNIQUE INDEX session_id_idx ON sessions(id)")
        db.execute("""CREATE TABLE votes_new (id TEXT PRIMARY KEY,
            responder TEXT REFERENCES users(id) ON DELETE SET NULL,
            recipient TEXT REFERENCES users(id) ON DELETE SET NULL,
            poll_id TEXT NOT NULL, day TEXT NOT NULL, timestamp TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0, question TEXT NOT NULL, UNIQUE(responder,poll_id,day))""")
        lookup = {q["id"]: q["question"] for q in questions}
        for row in db.execute("SELECT * FROM votes").fetchall():
            db.execute(
                "INSERT INTO votes_new VALUES (?,?,?,?,?,?,?,?)",
                tuple(
                    row[k]
                    for k in [
                        "id",
                        "responder",
                        "recipient",
                        "poll_id",
                        "day",
                        "timestamp",
                        "is_read",
                    ]
                )
                + (lookup.get(row["poll_id"], "A friend sent you a compliment."),),
            )
        db.execute("""CREATE TABLE reports_new (id TEXT PRIMARY KEY,
            reporter TEXT REFERENCES users(id) ON DELETE SET NULL,
            vote_id TEXT REFERENCES votes(id) ON DELETE SET NULL, reason TEXT NOT NULL, timestamp TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open', resolution TEXT NOT NULL DEFAULT '',
            resolved_at TEXT, subject_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            UNIQUE(reporter,vote_id))""")
        db.execute("""INSERT INTO reports_new (id,reporter,vote_id,reason,timestamp,subject_id)
            SELECT r.id,r.reporter,r.vote_id,r.reason,r.timestamp,v.responder FROM reports r LEFT JOIN votes v ON v.id=r.vote_id""")
        db.execute("DROP TABLE reports")
        db.execute("DROP TABLE votes")
        db.execute("ALTER TABLE votes_new RENAME TO votes")
        db.execute("ALTER TABLE reports_new RENAME TO reports")
        db.execute("CREATE INDEX inbox_idx ON votes(recipient,timestamp,id)")
        db.execute("""CREATE TABLE offers (user_id TEXT REFERENCES users(id) ON DELETE CASCADE, day TEXT NOT NULL,
            poll_id TEXT NOT NULL, question TEXT NOT NULL, emoji TEXT NOT NULL, color TEXT NOT NULL,
            options TEXT NOT NULL, position INTEGER NOT NULL, skipped INTEGER NOT NULL DEFAULT 0,
            shuffles INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id,day,poll_id))""")
        db.execute("""CREATE TABLE exposures (owner TEXT REFERENCES users(id) ON DELETE CASCADE,
            target TEXT REFERENCES users(id) ON DELETE CASCADE, day TEXT NOT NULL, count INTEGER NOT NULL,
            PRIMARY KEY(owner,target,day))""")
        db.execute("""CREATE TABLE ledger (id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            amount INTEGER NOT NULL, reason TEXT NOT NULL, timestamp TEXT NOT NULL, vote_id TEXT UNIQUE)""")
        db.execute(
            "INSERT INTO ledger SELECT lower(hex(randomblob(16))),id,coins,'Opening balance',strftime('%Y-%m-%dT%H:%M:%SZ','now'),NULL FROM users WHERE coins!=0"
        )
        db.execute(
            """CREATE TABLE invites (code TEXT PRIMARY KEY, owner TEXT REFERENCES users(id) ON DELETE CASCADE, expires REAL NOT NULL)"""
        )
        db.execute("""CREATE TABLE events (id INTEGER PRIMARY KEY, user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            event TEXT NOT NULL, day TEXT NOT NULL, UNIQUE(user_id,event,day))""")
        db.execute("""CREATE TABLE audit (id INTEGER PRIMARY KEY, action TEXT NOT NULL, target TEXT NOT NULL,
            note TEXT NOT NULL, timestamp TEXT NOT NULL)""")
        db.execute("CREATE INDEX users_school_idx ON users(school_id)")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("Migration failed foreign-key validation")
        db.execute(f"PRAGMA user_version={VERSION}")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def load_questions(path=None):
    path = Path(path or Path(__file__).with_name("content") / "questions.json")
    rows = json.loads(path.read_text())
    if not isinstance(rows, list) or len(rows) < 12:
        raise ValueError("Question catalog requires at least 12 entries")
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or any(
            not isinstance(row.get(k), str) or not row[k].strip()
            for k in ("id", "question", "emoji", "color")
        ):
            raise ValueError(
                "Each question requires id, question, emoji and color strings"
            )
        if row["id"] in ids or len(row["id"]) > 64 or len(row["question"]) > 200:
            raise ValueError("Duplicate question ID or oversized question")
        ids.add(row["id"])
    return rows


def import_schools(db, rows):
    """Validate the complete batch before writing; callers own the transaction."""
    batch = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each school must be an object")
        keys = ("id", "name", "englishName", "region", "address", "kind")
        if any(not isinstance(row.get(k, ""), str) for k in keys):
            raise ValueError("School fields must be strings")
        values = {k: row.get(k, "").strip() for k in keys}
        if any(not values[k] for k in ("id", "name", "region")) or values["id"] in seen:
            raise ValueError(
                "School IDs must be unique; id, name and region are required"
            )
        if len(values["id"]) > 100 or any(len(v) > 500 for v in values.values()):
            raise ValueError("School field too long")
        seen.add(values["id"])
        batch.append(
            (
                values["id"],
                values["name"],
                values["englishName"],
                values["region"],
                values["address"],
                values["kind"],
                normalize(" ".join(values.values())),
            )
        )
    if not batch:
        raise ValueError("Empty school catalog")
    db.executemany(
        """INSERT INTO schools (id,name,english_name,region,address,kind,search) VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET name=excluded.name,english_name=excluded.english_name,region=excluded.region,
        address=excluded.address,kind=excluded.kind,search=excluded.search,active=1""",
        batch,
    )
    db.execute(
        "UPDATE users SET school=(SELECT name FROM schools WHERE id=school_id) WHERE school_id IS NOT NULL"
    )
    return len(batch)
