"""Gas MVP API. Standard-library WSGI application; run behind TLS for deployment."""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

QUESTIONS = [
    ('1', 'Who would you like to go camping with?', '⛺️', 'brown'),
    ('2', 'Who always has a smile on their face?', '😊', 'blue'),
    ('3', 'Who is a great listener?', '👂', 'purple'),
    ('4', 'Who has a great sense of style?', '✨', 'pink'),
    ('5', 'Who gives the best music recommendations?', '🎵', 'blue'),
    ('6', 'Who is always fun to be around?', '😂', 'brown'),
    ('7', 'Who takes good care of the people around them?', '🌍', 'purple'),
    ('8', 'Who gives thoughtful advice?', '💡', 'blue'),
    ('9', 'Who encourages you to try something new?', '🏔', 'brown'),
    ('10', 'Who comes up with creative ideas?', '🎨', 'purple'),
    ('11', 'Who would you like to share a snack with?', '🍕', 'pink'),
    ('12', 'Who always has something kind to say?', '💬', 'blue'),
]
SCHEMA = '''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
 password TEXT NOT NULL, school TEXT NOT NULL, age INTEGER NOT NULL,
 coins INTEGER NOT NULL DEFAULT 0 CHECK(coins >= 0));
CREATE TABLE IF NOT EXISTS sessions (
 token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS friendships (
 sender TEXT REFERENCES users(id) ON DELETE CASCADE,
 recipient TEXT REFERENCES users(id) ON DELETE CASCADE,
 accepted INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(sender,recipient), CHECK(sender != recipient));
CREATE TABLE IF NOT EXISTS blocks (
 owner TEXT REFERENCES users(id) ON DELETE CASCADE,
 target TEXT REFERENCES users(id) ON DELETE CASCADE, hidden INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(owner,target));
CREATE TABLE IF NOT EXISTS votes (
 id TEXT PRIMARY KEY, responder TEXT REFERENCES users(id) ON DELETE CASCADE,
 recipient TEXT REFERENCES users(id) ON DELETE CASCADE,
 poll_id TEXT NOT NULL, day TEXT NOT NULL, timestamp TEXT NOT NULL,
 is_read INTEGER NOT NULL DEFAULT 0, UNIQUE(responder,poll_id,day));
CREATE INDEX IF NOT EXISTS inbox_idx ON votes(recipient,timestamp);
CREATE TABLE IF NOT EXISTS reports (
 id TEXT PRIMARY KEY, reporter TEXT REFERENCES users(id) ON DELETE CASCADE,
 vote_id TEXT REFERENCES votes(id) ON DELETE CASCADE, reason TEXT NOT NULL,
 timestamp TEXT NOT NULL, UNIQUE(reporter,vote_id));
CREATE TABLE IF NOT EXISTS rate_limits (
 key TEXT PRIMARY KEY, start REAL NOT NULL, count INTEGER NOT NULL);
'''

class APIError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message

def fail(status, message):
    raise APIError(status, message)

def field(data, name, minimum=1, maximum=100):
    value = data.get(name)
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        fail(400, f'{name}: {minimum}–{maximum} characters required')
    return value.strip()

def password_field(data):
    value = data.get('password')
    if not isinstance(value, str) or not 10 <= len(value) <= 128:
        fail(400, 'Password: 10–128 characters required')
    return value

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return salt + ':' + digest

def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')

def day_key():
    return datetime.now(timezone(timedelta(hours=9))).date().isoformat()

def public_user(row):
    return {k: row[k] for k in ('id', 'username', 'name', 'school')}

class Application:
    def __init__(self, database=None):
        self.database = str(database or os.environ.get('GAS_DATABASE', 'data/gas.sqlite3'))
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        db = self.connect()
        try:
            with db:
                db.executescript(SCHEMA)
        finally:
            db.close()
        self.dummy_hash = password_hash('unused dummy password')

    def connect(self):
        db = sqlite3.connect(self.database, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def __call__(self, environ, start_response):
        status = 200
        db = self.connect()
        try:
            method = environ.get('REQUEST_METHOD', 'GET')
            size = int(environ.get('CONTENT_LENGTH') or 0)
            if not 0 <= size <= 16384:
                fail(413, 'Request too large')
            data = {}
            if size:
                if environ.get('CONTENT_TYPE', '').split(';')[0] != 'application/json':
                    fail(415, 'Use application/json')
                try:
                    data = json.loads(environ['wsgi.input'].read(size))
                except (ValueError, UnicodeError):
                    fail(400, 'Invalid JSON')
                if not isinstance(data, dict):
                    fail(400, 'Expected JSON object')
            path = environ.get('PATH_INFO', '')
            if method == 'POST' and path in ('/v1/register', '/v1/login'):
                self.limit(db, 'auth:' + environ.get('REMOTE_ADDR', 'unknown'), 30, 600)
            token = environ.get('HTTP_AUTHORIZATION', '').removeprefix('Bearer ')
            query = parse_qs(environ.get('QUERY_STRING', ''))
            # Serialize mutations: duplicate votes and reciprocal friend requests are atomic.
            db.execute('BEGIN IMMEDIATE' if method != 'GET' else 'BEGIN')
            payload = self.route(db, method, path, data, token, query)
            db.commit()
        except APIError as error:
            db.rollback()
            status, payload = error.status, {'error': error.message}
        except (ValueError, OverflowError):
            db.rollback()
            status, payload = 400, {'error': 'Invalid request'}
        except Exception:
            db.rollback()
            import traceback
            traceback.print_exc()
            status, payload = 500, {'error': 'Server error'}
        finally:
            db.close()
        body = json.dumps(payload, ensure_ascii=False).encode()
        from http import HTTPStatus
        start_response(f'{status} {HTTPStatus(status).phrase}', [('Content-Type', 'application/json; charset=utf-8'), ('Content-Length', str(len(body))), ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff')])
        return [body]

    def limit(self, db, key, maximum, window):
        now = time.time()
        with db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM rate_limits WHERE start < ?', (now - window,))
            db.execute('INSERT INTO rate_limits VALUES (?, ?, 1) ON CONFLICT(key) DO UPDATE SET count=count+1', (key, now))
            count = db.execute('SELECT count FROM rate_limits WHERE key=?', (key,)).fetchone()[0]
        if count > maximum:
            fail(429, 'Too many attempts. Try again later.')

    def session(self, db, user_id):
        token = secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
        db.execute('INSERT INTO sessions VALUES (?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), user_id, time.time() + 30 * 86400))
        return {'token': token}

    def friends(self, db, uid):
        return db.execute('''SELECT u.* FROM users u JOIN friendships f
            ON (f.sender=? AND f.recipient=u.id) OR (f.recipient=? AND f.sender=u.id)
            WHERE f.accepted=1 ORDER BY u.username''', (uid, uid)).fetchall()

    def blocked(self, db, a, b):
        return db.execute('SELECT 1 FROM blocks WHERE (owner=? AND target=?) OR (owner=? AND target=?)', (a,b,b,a)).fetchone() is not None

    def route(self, db, method, path, data, token, query):
        if method == 'GET' and path == '/health':
            return {'status': 'ok'}
        if method == 'POST' and path in ('/v1/register', '/v1/login'):
            username = field(data, 'username', 3, 24).lower()
            password = password_field(data)
            if not re.fullmatch(r'[a-z0-9_]{3,24}', username):
                fail(400, 'Username: use 3–24 letters, numbers or underscores')
            if path.endswith('/login'):
                row = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
                stored = row['password'] if row else self.dummy_hash
                valid = hmac.compare_digest(stored, password_hash(password, stored.split(':')[0]))
                if not row or not valid:
                    fail(401, 'Incorrect username or password')
                return self.session(db, row['id'])
            name = field(data, 'name', 1, 40)
            school = ' '.join(field(data, 'school', 2, 100).split())
            age = data.get('age')
            if type(age) is not int or not 14 <= age <= 19:
                fail(400, 'This MVP is available for ages 14–19')
            uid = secrets.token_hex(16)
            try:
                db.execute('INSERT INTO users (id,username,name,password,school,age) VALUES (?,?,?,?,?,?)', (uid,username,name,password_hash(password),school,age))
            except sqlite3.IntegrityError:
                fail(409, 'Username is already taken')
            return self.session(db, uid)
        row = db.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>?', (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
        if not row:
            fail(401, 'Please sign in again')
        uid = row['id']
        if path == '/v1/me' and method == 'GET':
            return dict(public_user(row), age=row['age'], coins=row['coins'])
        if path == '/v1/me' and method == 'DELETE':
            password = password_field(data)
            if not hmac.compare_digest(row['password'], password_hash(password, row['password'].split(':')[0])):
                fail(403, 'Incorrect password')
            db.execute('DELETE FROM users WHERE id=?', (uid,))
            return {'ok': True}
        if path == '/v1/logout' and method == 'POST':
            db.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(token.encode()).hexdigest(),))
            return {'ok': True}
        if path == '/v1/schools' and method == 'GET':
            text = query.get('q', [''])[0][:100]
            return {'schools': [r[0] for r in db.execute('SELECT DISTINCT school FROM users WHERE instr(lower(school),lower(?))>0 ORDER BY school LIMIT 30', (text,))]}
        if path == '/v1/people' and method == 'GET':
            term = query.get('q', [''])[0].lower()
            if len(term) < 3:
                return {'people': []}
            people = db.execute('SELECT * FROM users WHERE school=? AND id!=? AND username=? LIMIT 1', (row['school'], uid, term))
            return {'people': [public_user(p) for p in people if not self.blocked(db,uid,p['id'])]}
        if path == '/v1/friends' and method == 'GET':
            requests = db.execute('SELECT u.* FROM users u JOIN friendships f ON f.sender=u.id WHERE f.recipient=? AND f.accepted=0', (uid,))
            sent = db.execute('SELECT u.* FROM users u JOIN friendships f ON f.recipient=u.id WHERE f.sender=? AND f.accepted=0', (uid,))
            return {'friends': [public_user(f) for f in self.friends(db,uid)], 'requests': [public_user(f) for f in requests], 'sent': [public_user(f) for f in sent]}
        if path in ('/v1/friends', '/v1/blocks') and method in ('POST','DELETE'):
            target = field(data, 'userId')
            other = db.execute('SELECT * FROM users WHERE id=?', (target,)).fetchone()
            if not other or target == uid or (path == '/v1/friends' and (other['school'] != row['school'] or self.blocked(db,uid,target))):
                fail(404, 'User unavailable')
            if path == '/v1/blocks':
                if method == 'POST':
                    db.execute('INSERT OR IGNORE INTO blocks (owner,target) VALUES (?,?)', (uid,target))
                    db.execute('DELETE FROM friendships WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?)', (uid,target,target,uid))
                else:
                    db.execute('DELETE FROM blocks WHERE owner=? AND target=?', (uid,target))
            elif method == 'DELETE':
                db.execute('DELETE FROM friendships WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?)', (uid,target,target,uid))
            else:
                reverse = db.execute('SELECT 1 FROM friendships WHERE sender=? AND recipient=?', (target,uid)).fetchone()
                if reverse:
                    db.execute('UPDATE friendships SET accepted=1 WHERE sender=? AND recipient=?', (target,uid))
                else:
                    db.execute('INSERT OR IGNORE INTO friendships VALUES (?,?,0)', (uid,target))
            return {'ok': True}
        if path == '/v1/blocks' and method == 'GET':
            return {'people': [public_user(p) for p in db.execute('SELECT u.* FROM users u JOIN blocks b ON b.target=u.id WHERE b.owner=? AND b.hidden=0', (uid,))]}
        if path == '/v1/polls' and method == 'GET':
            friends = self.friends(db, uid)
            answered = {r[0] for r in db.execute('SELECT poll_id FROM votes WHERE responder=? AND day=?', (uid,day_key()))}
            polls = []
            if friends:
                for index, (pid, question, emoji, color) in enumerate(QUESTIONS):
                    if pid in answered:
                        continue
                    rotated = friends[index % len(friends):] + friends[:index % len(friends)]
                    options = [{'id': f['id'], 'userId': f['id'], 'userName': f['name']} for f in rotated[:4]]
                    polls.append(dict(id=pid, question=question, emoji=emoji, backgroundColor=color, options=options))
            return {'polls': polls, 'answered': len(answered), 'total': len(QUESTIONS)}
        if path == '/v1/votes' and method == 'POST':
            pid, target = field(data,'pollId'), field(data,'selectedUserId')
            if pid not in {p[0] for p in QUESTIONS}:
                fail(404, 'Poll not found')
            # Validate against the same offered options, not merely any known account.
            polls = self.route(db, 'GET', '/v1/polls', {}, token, {})['polls']
            offered = next((p for p in polls if p['id']==pid), None)
            if not offered:
                fail(409, 'Poll already answered or unavailable')
            if target not in {o['userId'] for o in offered['options']}:
                fail(403, 'Choose an available friend')
            db.execute('INSERT INTO votes VALUES (?,?,?,?,?,?,0)', (secrets.token_hex(16),uid,target,pid,day_key(),timestamp()))
            db.execute('UPDATE users SET coins=coins+20 WHERE id=?', (uid,))
            return {'coinsEarned': 20}
        if path == '/v1/inbox' and method == 'GET':
            questions = {p[0]: p[1] for p in QUESTIONS}
            # Never serialize responder IDs, gender, or exact vote times to recipients.
            votes = db.execute('SELECT * FROM votes WHERE recipient=? ORDER BY timestamp DESC LIMIT 200', (uid,))
            return {'flames': [dict(id=v['id'], pollQuestion=questions[v['poll_id']], day=v['day'], isRead=bool(v['is_read'])) for v in votes if not self.blocked(db,uid,v['responder'])]}
        if path in ('/v1/inbox/read', '/v1/reports') and method == 'POST':
            vid = field(data,'id')
            vote = db.execute('SELECT * FROM votes WHERE id=? AND recipient=?', (vid,uid)).fetchone()
            if not vote:
                fail(404, 'Compliment not found')
            if path.endswith('/read'):
                db.execute('UPDATE votes SET is_read=1 WHERE id=?', (vid,))
            else:
                reason = field(data,'reason',3,500)
                db.execute('INSERT OR IGNORE INTO reports VALUES (?,?,?,?,?)', (secrets.token_hex(16),uid,vid,reason,timestamp()))
                db.execute('INSERT INTO blocks (owner,target,hidden) VALUES (?,?,1) ON CONFLICT(owner,target) DO UPDATE SET hidden=1', (uid,vote['responder']))
                db.execute('DELETE FROM friendships WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?)', (uid,vote['responder'],vote['responder'],uid))
            return {'ok': True}
        fail(404, 'Endpoint not found')

if __name__ == '__main__':
    app = Application()
    host, port = os.environ.get('GAS_HOST', '127.0.0.1'), int(os.environ.get('PORT', '8080'))
    print(f'Gas development API on http://{host}:{port}', flush=True)
    with make_server(host, port, app) as server:
        server.serve_forever()
