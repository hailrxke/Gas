"""Local operator tools. Run on the server as the database owner."""

import argparse
import csv
import json
import os
import sqlite3
from pathlib import Path
from app import Application
from common import timestamp
from storage import import_schools


def backup(source, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest)
        if dest.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Backup failed integrity check")
    except Exception:
        dest.close()
        target.unlink(missing_ok=True)
        raise
    finally:
        dest.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", default=os.environ.get("GAS_DATABASE", "data/gas.sqlite3")
    )
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("init")
    imp = sub.add_parser("import-schools")
    imp.add_argument("file")
    b = sub.add_parser("backup")
    b.add_argument("destination")
    reports = sub.add_parser("reports")
    reports.add_argument(
        "--status",
        choices=["open", "closed", "dismissed", "action_taken"],
        default="open",
    )
    resolve = sub.add_parser("resolve")
    resolve.add_argument("report_id")
    resolve.add_argument(
        "--status", choices=["closed", "dismissed", "action_taken"], required=True
    )
    resolve.add_argument("--message", required=True)
    for name in ["suspend", "unsuspend", "revoke"]:
        p = sub.add_parser(name)
        p.add_argument("user_id")
        p.add_argument("--reason", default="Operator action")
    mapping = sub.add_parser("map-school")
    mapping.add_argument("old_id")
    mapping.add_argument("new_id")
    sub.add_parser("metrics")
    prune = sub.add_parser("prune")
    prune.add_argument("--backup", required=True)
    args = parser.parse_args()
    if (
        args.action not in ("init", "import-schools")
        and not Path(args.database).is_file()
    ):
        parser.error(
            "Database does not exist; initialize or select the correct source first"
        )
    app = Application(args.database)
    db = app.connect()
    try:
        if args.action in ("backup", "prune"):
            backup(db, args.destination if args.action == "backup" else args.backup)
        with db:
            if args.action == "init":
                print(
                    "Database initialized; import a school catalog before registration."
                )
            elif args.action == "import-schools":
                p = Path(args.file)
                if p.suffix.lower() == ".csv":
                    with p.open(newline="", encoding="utf-8-sig") as stream:
                        rows = list(csv.DictReader(stream))
                else:
                    rows = json.loads(p.read_text())
                print(f"Imported {import_schools(db, rows)} schools")
            elif args.action == "reports":
                rows = db.execute(
                    "SELECT id,reporter,subject_id,reason,timestamp,status FROM reports WHERE status=? ORDER BY timestamp LIMIT 100",
                    (args.status,),
                )
                print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))
            elif args.action == "resolve":
                if not 3 <= len(args.message) <= 500:
                    parser.error("Use a 3–500 character public resolution message")
                if not db.execute(
                    "UPDATE reports SET status=?,resolution=?,resolved_at=? WHERE id=?",
                    (args.status, args.message, timestamp(), args.report_id),
                ).rowcount:
                    parser.error("Report not found")
                db.execute(
                    "INSERT INTO audit (action,target,note,timestamp) VALUES (?,?,?,?)",
                    ("resolve", args.report_id, args.status, timestamp()),
                )
                print("Report updated; the reporter can see the resolution message.")
            elif args.action in ("suspend", "unsuspend", "revoke"):
                if not db.execute(
                    "SELECT 1 FROM users WHERE id=?", (args.user_id,)
                ).fetchone():
                    parser.error("User not found")
                if args.action != "revoke":
                    db.execute(
                        "UPDATE users SET suspended=? WHERE id=?",
                        (int(args.action == "suspend"), args.user_id),
                    )
                    app.invalidate_options(db, args.user_id)
                if args.action != "unsuspend":
                    db.execute("DELETE FROM sessions WHERE user_id=?", (args.user_id,))
                db.execute(
                    "INSERT INTO audit (action,target,note,timestamp) VALUES (?,?,?,?)",
                    (args.action, args.user_id, args.reason[:500], timestamp()),
                )
                print("Account updated.")
            elif args.action == "map-school":
                school = db.execute(
                    "SELECT * FROM schools WHERE id=? AND active=1", (args.new_id,)
                ).fetchone()
                if not school:
                    parser.error("Destination school must be active")
                old = db.execute(
                    "SELECT source FROM schools WHERE id=?", (args.old_id,)
                ).fetchone()
                if not old or old["source"] != "legacy":
                    parser.error("Only legacy schools can be mapped")
                rows = db.execute(
                    "SELECT id FROM users WHERE school_id=?", (args.old_id,)
                ).fetchall()
                for row in rows:
                    app.invalidate_options(db, row["id"])
                db.execute(
                    "UPDATE users SET school_id=?,school=? WHERE school_id=?",
                    (args.new_id, school["name"], args.old_id),
                )
                print(f"Mapped {len(rows)} accounts. Enrollment remains unverified.")
            elif args.action == "metrics":
                metrics = dict(
                    users=db.execute("SELECT count(*) FROM users").fetchone()[0],
                    openReports=db.execute(
                        "SELECT count(*) FROM reports WHERE status='open'"
                    ).fetchone()[0],
                    daily=[
                        dict(r)
                        for r in db.execute(
                            "SELECT day,event,count(*) users FROM events GROUP BY day,event ORDER BY day DESC LIMIT 120"
                        )
                    ],
                )
                for days in (1, 7):
                    metrics[f"day{days}Retention"] = [
                        dict(r)
                        for r in db.execute(
                            """SELECT r.day cohort,count(*) registered,
                        SUM(EXISTS(SELECT 1 FROM events a WHERE a.user_id=r.user_id AND a.event='active' AND a.day=date(r.day,?))) returned
                        FROM events r WHERE r.event='registered' AND r.day<=date('now','+9 hours',?) GROUP BY r.day ORDER BY r.day DESC LIMIT 30""",
                            (f"+{days} days", f"-{days} days"),
                        )
                    ]
                print(json.dumps(metrics, indent=2))
            elif args.action == "prune":
                db.execute(
                    "DELETE FROM sessions WHERE expires<CAST(strftime('%s','now') AS INTEGER)"
                )
                db.execute(
                    "DELETE FROM invites WHERE expires<CAST(strftime('%s','now') AS INTEGER)"
                )
                db.execute(
                    "DELETE FROM rate_limits WHERE start<CAST(strftime('%s','now') AS INTEGER)-86400"
                )
                db.execute(
                    "DELETE FROM offers WHERE day<date('now','+9 hours','-30 days')"
                )
                db.execute(
                    "DELETE FROM exposures WHERE day<date('now','+9 hours','-30 days')"
                )
                db.execute(
                    "DELETE FROM events WHERE day<date('now','+9 hours','-90 days')"
                )
                db.execute(
                    "DELETE FROM reports WHERE timestamp<strftime('%Y-%m-%dT%H:%M:%SZ','now','-90 days')"
                )
                db.execute(
                    "DELETE FROM audit WHERE timestamp<strftime('%Y-%m-%dT%H:%M:%SZ','now','-90 days')"
                )
                db.execute(
                    "DELETE FROM votes WHERE day<date('now','+9 hours','-365 days')"
                )
                print(
                    "Expired records removed. Coin ledger and account balances retained."
                )
            elif args.action == "backup":
                print("Backup passed integrity check.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
