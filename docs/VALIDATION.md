# Validation record

Verified in the Linux workspace on 2026-09-25:

- **13 API tests passed** with Python 3.14.7 using real temporary SQLite databases. Coverage includes concurrent duplicate votes, exact password preservation, malformed/oversized requests, unauthorized reads, school separation, consent, blocking, anonymous reports, session expiry, persistence and cascading account deletion.
- **HTTP smoke test passed** against Gunicorn 26.2.0 with two worker processes and a temporary database. It registers two users, accepts a friendship, submits a vote, checks coins and anonymous delivery, then deletes the sender and verifies related records disappear.
- **17 Swift source files parsed without syntax errors** using tree-sitter-swift 0.7.3. This is a syntax check, not Swift type checking or an iOS build.
- Xcode project generation is deterministic. `Info.plist` and the shared scheme parse successfully. `git diff --check` passed.

The first multiworker HTTP trial without preloading had a transient connection refusal; ten repeat trials passed. The final documented configuration uses `--preload` to initialize the application/database before workers start, and its HTTP smoke test passed.

Not verified in this environment:

- Xcode compilation, simulator execution, device signing and Keychain/ATS behavior on an actual iPhone. Xcode and Apple SDKs are unavailable on Linux.
- GitHub Actions execution: the workflow is added locally but has not been pushed or run remotely.
- Public deployment, HTTPS/domain provisioning or App Store distribution.

Reproduce server checks from the repository root:

```sh
python3 -m unittest discover -s server -v
python3 -m venv .venv
.venv/bin/pip install -r server/requirements.txt
.venv/bin/python scripts/smoke_http.py
```

On a Mac, complete the simulator build and two-user walkthrough in `README.md`. The CI workflow also builds the simulator target when run on GitHub.
