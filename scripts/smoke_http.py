#!/usr/bin/env python3
"""Exercise a real, multiworker HTTP server with five accounts and a private database."""

import json
import os
from datetime import date
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]


def run():
    with tempfile.TemporaryDirectory(prefix="gas-smoke-") as temporary:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        database = str(Path(temporary) / "gas.sqlite3")
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "server/manage.py"),
                "--database",
                database,
                "import-schools",
                str(ROOT / "server/examples/schools.json"),
            ],
            check=True,
        )
        env = dict(os.environ, GAS_DATABASE=database)
        # Store logs in a temporary file to avoid filling a pipe while serving requests.
        with tempfile.TemporaryFile() as logs:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "gunicorn",
                    "--chdir",
                    str(ROOT / "server"),
                    "--bind",
                    f"127.0.0.1:{port}",
                    "--preload",
                    "--workers",
                    "2",
                    "--threads",
                    "2",
                    "wsgi:application",
                ],
                env=env,
                stdout=logs,
                stderr=logs,
            )

            def call(path, method="GET", body=None, token=""):
                request = urllib.request.Request(
                    f"http://127.0.0.1:{port}{path}",
                    data=json.dumps(body).encode() if body is not None else None,
                    method=method,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + token,
                    },
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    assert response.headers["X-Request-ID"]
                    return json.load(response)

            try:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError("Server exited before becoming ready")
                    try:
                        call("/health")
                        break
                    except urllib.error.URLError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError("Server did not become ready")
                config = call("/v1/config")
                school = call("/v1/schools?q=Demo")["schools"][0]["id"]
                accounts = []
                for i in range(5):
                    username = f"student_{i}"
                    result = call(
                        "/v1/register",
                        "POST",
                        dict(
                            username=username,
                            password="smoke test password",
                            name=username,
                            schoolId=school,
                            birthDate=f"{date.today().year - 16}-01-01",
                            consent=True,
                            consentVersion=config["consentVersion"],
                        ),
                    )
                    accounts.append(
                        (result["token"], call("/v1/me", token=result["token"])["id"])
                    )
                a, aid = accounts[0]
                for b, bid in accounts[1:]:
                    call("/v1/friends", "POST", {"userId": bid}, a)
                    call("/v1/friends", "POST", {"userId": aid}, b)
                state = call("/v1/polls", token=a)
                poll = state["polls"][0]
                target = poll["options"][0]["userId"]
                b = next(t for t, uid in accounts if uid == target)
                call(
                    "/v1/polls/skip",
                    "POST",
                    dict(pollId=poll["id"], day=state["day"]),
                    a,
                )
                assert call("/v1/polls", token=a)["skipped"] == 1
                call("/v1/polls/restore", "POST", dict(day=state["day"]), a)
                vote = dict(pollId=poll["id"], selectedUserId=target, day=state["day"])
                assert call("/v1/votes", "POST", vote, a)["coinsEarned"] == 20
                try:
                    call("/v1/votes", "POST", vote, a)
                    raise AssertionError("Duplicate vote was accepted")
                except urllib.error.HTTPError as error:
                    assert error.code == 409
                flames = call("/v1/inbox", token=b)["flames"]
                assert len(flames) == 1 and set(flames[0]) == {
                    "id",
                    "pollQuestion",
                    "day",
                    "isRead",
                }
                call("/v1/inbox/read", "POST", dict(id=flames[0]["id"]), b)
                assert call("/v1/inbox", token=b)["unreadCount"] == 0
                assert call("/v1/me", token=a)["coins"] == 20
                assert len(call("/v1/ledger", token=a)["entries"]) == 1
                exported = call(
                    "/v1/export", "POST", dict(password="smoke test password"), a
                )
                assert len(exported["sentVotes"]) == 1
                call("/v1/me", "DELETE", dict(password="smoke test password"), a)
                assert call("/v1/friends", token=b)["friends"] == []
                assert len(call("/v1/inbox", token=b)["flames"]) == 1
                print(
                    "HTTP smoke PASS: five accounts, school catalog, friendships, persistent polls, atomic reward, private inbox, export and anonymized deletion"
                )
            except Exception:
                logs.seek(0)
                print(logs.read().decode(), file=sys.stderr)
                raise
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    run()
