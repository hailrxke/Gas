import hashlib
import hmac
import secrets
from datetime import date, datetime, timezone, timedelta

KOREA = timezone(timedelta(hours=9))
CONSENT_VERSION = "2026-09-27"
MIN_FRIENDS = 4


class APIError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def fail(status, message):
    raise APIError(status, message)


def field(data, name, minimum=1, maximum=100):
    value = data.get(name)
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        fail(400, f"{name}: {minimum}–{maximum} characters required")
    return value.strip()


def password_field(data, name="password"):
    value = data.get(name)
    if not isinstance(value, str) or not 10 <= len(value) <= 128:
        fail(400, "Password: 10–128 characters required")
    return value


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return (
        salt
        + ":"
        + hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
        ).hex()
    )


def verify_password(data, row):
    password = password_field(data)
    if not hmac.compare_digest(
        row["password"], password_hash(password, row["password"].split(":")[0])
    ):
        fail(403, "Incorrect password")


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def timestamp():
    return (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


def day_key():
    return datetime.now(KOREA).date().isoformat()


def age_on(birth, today=None):
    today = today or datetime.now(KOREA).date()
    birth = date.fromisoformat(birth)
    return (
        today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    )


def birth_date(data):
    value = field(data, "birthDate", 10, 10)
    try:
        age = age_on(value)
    except ValueError:
        fail(400, "Enter a valid birth date (YYYY-MM-DD)")
    if not 14 <= age <= 19:
        fail(400, "Registration is available for ages 14–19")
    return value, age


def public_user(row):
    return dict(
        id=row["id"],
        username=row["username"],
        name=row["name"],
        school=row["school"],
        schoolId=row["school_id"],
    )


def own_user(row):
    return dict(
        public_user(row),
        age=age_on(row["birth_date"]) if row["birth_date"] else row["age"],
        birthDate=row["birth_date"],
        coins=row["coins"],
        hasRecoveryCode=bool(row["recovery_hash"]),
        consentVersion=row["consent_version"],
    )


def event(db, uid, name):
    db.execute(
        "INSERT OR IGNORE INTO events (user_id,event,day) VALUES (?,?,?)",
        (uid, name, day_key()),
    )
