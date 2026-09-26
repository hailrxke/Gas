"""Gas API: WSGI application; development runner below, Gunicorn for deployment."""

import ipaddress
import json
import logging
import os
import secrets
import sqlite3
import time
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server
from accounts import Accounts
from common import (
    APIError,
    CONSENT_VERSION,
    day_key,
    fail,
    password_hash,
    timestamp,
    token_hash,
)
from polls import Polls
from social import Social
from storage import initialize, load_questions


class Application(Accounts, Polls, Social):
    def __init__(self, database=None, questions_path=None):
        self.database = str(
            database or os.environ.get("GAS_DATABASE", "data/gas.sqlite3")
        )
        self.questions = load_questions(
            questions_path or os.environ.get("GAS_QUESTIONS")
        )
        initialize(self.database, self.questions)
        self.dummy_hash = password_hash("unused dummy password")
        self.dummy_recovery = token_hash(secrets.token_hex(16))
        self.trusted_proxies = set(
            filter(None, os.environ.get("GAS_TRUSTED_PROXIES", "").split(","))
        )

    def today(self):
        return day_key()

    def connect(self):
        db = sqlite3.connect(self.database, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def limit(self, db, key, maximum, window):
        now = time.time()
        with db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM rate_limits WHERE start<?", (now - 86400,))
            row = db.execute(
                "SELECT start,count FROM rate_limits WHERE key=?", (key,)
            ).fetchone()
            if not row or row["start"] <= now - window:
                count = 1
                db.execute(
                    "INSERT OR REPLACE INTO rate_limits VALUES (?,?,1)", (key, now)
                )
            else:
                count = row["count"] + 1
                db.execute("UPDATE rate_limits SET count=? WHERE key=?", (count, key))
        if count > maximum:
            fail(429, "Too many requests. Please wait and try again.")

    def __call__(self, environ, start_response):
        status = 200
        db = None
        started = time.monotonic()
        request_id = secrets.token_hex(8)
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "")
        try:
            db = self.connect()
            size = int(environ.get("CONTENT_LENGTH") or 0)
            if not 0 <= size <= 16384:
                fail(413, "Request too large")
            data = {}
            if size:
                if environ.get("CONTENT_TYPE", "").split(";")[0] != "application/json":
                    fail(415, "Use application/json")
                try:
                    data = json.loads(environ["wsgi.input"].read(size))
                except (ValueError, UnicodeError):
                    fail(400, "Invalid JSON")
                if not isinstance(data, dict):
                    fail(400, "Expected JSON object")
            remote = environ.get("REMOTE_ADDR", "unknown")
            if remote in self.trusted_proxies:
                try:
                    remote = str(
                        ipaddress.ip_address(environ.get("HTTP_X_REAL_IP", remote))
                    )
                except ValueError:
                    fail(400, "Invalid proxy client address")
            if method == "POST" and path in (
                "/v1/register",
                "/v1/login",
                "/v1/recover",
            ):
                self.limit(db, "auth:" + token_hash(remote), 30, 600)
                # Per-account throttling also applies across IP addresses.
                name = str(data.get("username", "")).strip().lower()
                if path != "/v1/register":
                    self.limit(db, "account:" + token_hash(name), 15, 600)
            else:
                self.limit(db, "request:" + token_hash(remote), 600, 60)
            authorization = environ.get("HTTP_AUTHORIZATION", "")
            token = authorization[7:] if authorization.startswith("Bearer ") else ""
            query = parse_qs(environ.get("QUERY_STRING", ""))
            # Poll reads allocate persistent offers and count exposure, so they also require a write transaction.
            db.execute(
                "BEGIN IMMEDIATE" if method != "GET" or path == "/v1/polls" else "BEGIN"
            )
            if method == "GET" and path == "/health":
                db.execute("SELECT 1 FROM users LIMIT 1")
                payload = {
                    "status": "ok",
                    "schemaVersion": db.execute("PRAGMA user_version").fetchone()[0],
                }
            else:
                payload = self.route(db, method, path, data, token, query)
            db.commit()
        except APIError as error:
            if db:
                db.rollback()
            status, payload = (
                error.status,
                {"error": error.message, "requestId": request_id},
            )
        except (ValueError, OverflowError):
            if db:
                db.rollback()
            status, payload = 400, {"error": "Invalid request", "requestId": request_id}
        except sqlite3.OperationalError:
            if db:
                db.rollback()
            logging.exception("Database unavailable request_id=%s", request_id)
            status, payload = (
                503,
                {
                    "error": "Service temporarily unavailable. Please retry.",
                    "requestId": request_id,
                },
            )
        except Exception:
            if db:
                db.rollback()
            logging.exception("Request failed request_id=%s", request_id)
            status, payload = 500, {"error": "Server error", "requestId": request_id}
        finally:
            if db:
                db.close()
        body = json.dumps(payload, ensure_ascii=False).encode()
        from http import HTTPStatus

        headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("X-Request-ID", request_id),
        ]
        if status in (429, 503):
            headers.append(("Retry-After", "60"))
        # Excludes URL queries, request bodies, IP addresses and authorization credentials.
        logging.info(
            json.dumps(
                dict(
                    requestId=request_id,
                    method=method,
                    status=status,
                    durationMs=round((time.monotonic() - started) * 1000),
                )
            )
        )
        start_response(f"{status} {HTTPStatus(status).phrase}", headers)
        return [body]

    def route(self, db, method, path, data, token, query):
        public = self.public_route(db, method, path, data, query)
        if public is not None:
            return public
        session = db.execute(
            "SELECT * FROM sessions WHERE token=? AND expires>?",
            (token_hash(token), time.time()),
        ).fetchone()
        if not session:
            fail(401, "Please sign in again")
        row = db.execute(
            "SELECT * FROM users WHERE id=?", (session["user_id"],)
        ).fetchone()
        if not row or row["suspended"]:
            fail(401, "This session is no longer available")
        if (
            path
            not in ("/v1/logout", "/v1/me", "/v1/consent", "/v1/export", "/v1/config")
            and row["consent_version"] != CONSENT_VERSION
        ):
            fail(428, "Please accept the updated privacy information in your profile")
        if path == "/v1/consent" and method == "POST":
            if (
                data.get("consent") is not True
                or data.get("consentVersion") != CONSENT_VERSION
            ):
                fail(400, "Accept the current privacy information")
            db.execute(
                "UPDATE users SET consent_version=?,consent_at=? WHERE id=?",
                (CONSENT_VERSION, timestamp(), row["id"]),
            )
            return {"ok": True}
        result = self.account_route(db, method, path, data, row, session)
        if result is None:
            result = self.social_route(db, method, path, data, row, query)
        if result is None:
            result = self.poll_route(db, method, path, data, row, query)
        if result is None:
            fail(404, "Endpoint not found")
        return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    app = Application()
    host, port = (
        os.environ.get("GAS_HOST", "127.0.0.1"),
        int(os.environ.get("PORT", "8080")),
    )
    print(f"Gas development API on http://{host}:{port}", flush=True)
    with make_server(host, port, app) as server:
        server.serve_forever()
