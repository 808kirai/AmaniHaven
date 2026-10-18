import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.privacy import encrypt, hash_phone, normalize_msisdn
from app.triage.rules import tier_rank

# sqlite keeps the pilot simple, the queries stay plain so moving to postgres later is easy
schema = """
create table if not exists users (
    user_hash        text primary key,
    phone_enc        text,
    language         text not null default 'sw',
    pending_state    text,
    opted_out        integer not null default 0,
    callback_consent integer not null default 0,
    tip_cursor       integer not null default 0,
    created_at       text not null,
    last_seen        text not null
);
create table if not exists messages (
    id         integer primary key autoincrement,
    user_hash  text not null,
    direction  text not null check (direction in ('in', 'out')),
    channel    text not null,
    body_enc   text not null,
    tier       text,
    created_at text not null
);
create index if not exists idx_messages_user on messages (user_hash, created_at);
create table if not exists cases (
    id          integer primary key autoincrement,
    user_hash   text not null,
    tier        text not null,
    source      text not null,
    reason      text,
    status      text not null default 'open' check (status in ('open', 'claimed', 'closed')),
    claimed_by  text,
    note_enc    text,
    created_at  text not null,
    updated_at  text not null
);
create index if not exists idx_cases_status on cases (status, tier);
create table if not exists checkins (
    id         integer primary key autoincrement,
    user_hash  text not null,
    phq4       integer not null,
    safety_yes integer not null,
    created_at text not null
);
create table if not exists events (
    id         integer primary key autoincrement,
    kind       text not null,
    tier       text,
    channel    text,
    created_at text not null
);
create table if not exists audit_log (
    id         integer primary key autoincrement,
    actor      text not null,
    action     text not null,
    case_id    integer,
    created_at text not null
);
"""

# one connection per thread, and the schema is created once per database file
_local = threading.local()
_init_lock = threading.Lock()
_initialized = set()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _since(delta):
    return (datetime.now(timezone.utc) - delta).isoformat(timespec="seconds")


def _connect():
    path = get_settings().database_path
    conn = getattr(_local, "conn", None)
    if conn is None or getattr(_local, "path", None) != path:
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys = on")
        conn.execute("pragma journal_mode = wal")
        _local.conn, _local.path = conn, path
    with _init_lock:
        if path not in _initialized:
            conn.executescript(schema)
            _initialized.add(path)
    return conn


@contextmanager
def tx():
    # commit when the block finishes, roll back if it raises
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def reset_for_tests():
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
    _local.conn = None
    _initialized.clear()


# users


def get_or_create_user(phone):
    user_hash = hash_phone(phone)
    with tx() as c:
        row = c.execute("select * from users where user_hash = ?", (user_hash,)).fetchone()
        if row is None:
            ts = now()
            c.execute(
                "insert into users (user_hash, phone_enc, language, created_at, last_seen) values (?, ?, ?, ?, ?)",
                (user_hash, encrypt(normalize_msisdn(phone)), get_settings().default_language, ts, ts),
            )
            log_event(c, "new_user")
        else:
            c.execute("update users set last_seen = ? where user_hash = ?", (now(), user_hash))
        return c.execute("select * from users where user_hash = ?", (user_hash,)).fetchone()


def get_user(user_hash):
    with tx() as c:
        return c.execute("select * from users where user_hash = ?", (user_hash,)).fetchone()


# only these columns can be changed, so field names never come from outside
_user_fields = {"language", "pending_state", "opted_out", "callback_consent", "tip_cursor"}


def update_user(user_hash, **fields):
    unknown = set(fields) - _user_fields
    if unknown:
        raise ValueError(f"unknown user fields {unknown}")
    assignments = ", ".join(f"{k} = ?" for k in fields)
    with tx() as c:
        c.execute(f"update users set {assignments} where user_hash = ?", (*fields.values(), user_hash))


def delete_user_data(user_hash):
    # right to erasure, removes everything tied to this person
    # the events table holds anonymous counts with no link to anyone, so it stays
    with tx() as c:
        for table in ("messages", "cases", "checkins", "users"):
            c.execute(f"delete from {table} where user_hash = ?", (user_hash,))
        log_event(c, "data_deleted")


# messages


def save_message(user_hash, direction, channel, body, tier=None):
    with tx() as c:
        c.execute(
            "insert into messages (user_hash, direction, channel, body_enc, tier, created_at) values (?, ?, ?, ?, ?, ?)",
            (user_hash, direction, channel, encrypt(body), tier, now()),
        )


def recent_messages(user_hash, limit=10):
    # oldest first so the thread reads top to bottom
    with tx() as c:
        rows = c.execute(
            "select * from messages where user_hash = ? order by id desc limit ?", (user_hash, limit)
        ).fetchall()
    return list(reversed(rows))


def outbound_count_since(user_hash, delta):
    with tx() as c:
        return c.execute(
            "select count(*) from messages where user_hash = ? and direction = 'out' and created_at >= ?",
            (user_hash, _since(delta)),
        ).fetchone()[0]


def inbound_tier_count_since(user_hash, tier, delta):
    with tx() as c:
        return c.execute(
            "select count(*) from messages where user_hash = ? and direction = 'in' and tier = ? and created_at >= ?",
            (user_hash, tier, _since(delta)),
        ).fetchone()[0]


# cases


def open_case(user_hash, tier, source, reason):
    # one open case per person, so counselors see one card however many messages arrive
    # returns the case id and whether counselors need an alert, which is when the case is new or its tier rose
    with tx() as c:
        existing = c.execute(
            "select * from cases where user_hash = ? and status != 'closed' order by id desc limit 1", (user_hash,)
        ).fetchone()
        if existing:
            raised = tier_rank[tier] > tier_rank[existing["tier"]]
            c.execute(
                "update cases set tier = ?, reason = ?, updated_at = ? where id = ?",
                (tier if raised else existing["tier"], reason, now(), existing["id"]),
            )
            if raised:
                log_event(c, "case_escalated", tier=tier, channel=source)
            return existing["id"], raised
        ts = now()
        cur = c.execute(
            "insert into cases (user_hash, tier, source, reason, created_at, updated_at) values (?, ?, ?, ?, ?, ?)",
            (user_hash, tier, source, reason, ts, ts),
        )
        log_event(c, "case_opened", tier=tier, channel=source)
        return cur.lastrowid, True


def list_cases(status=None):
    # most urgent first, then oldest first
    order = "case tier when 'crisis' then 0 when 'safeguarding' then 1 when 'elevated' then 2 else 3 end, created_at"
    with tx() as c:
        if status:
            return c.execute(f"select * from cases where status = ? order by {order}", (status,)).fetchall()
        return c.execute(f"select * from cases where status != 'closed' order by {order}").fetchall()


def get_case(case_id):
    with tx() as c:
        return c.execute("select * from cases where id = ?", (case_id,)).fetchone()


def update_case(case_id, **fields):
    if set(fields) - {"status", "claimed_by", "note_enc", "tier"}:
        raise ValueError("unknown case fields")
    assignments = ", ".join(f"{k} = ?" for k in fields)
    with tx() as c:
        c.execute(f"update cases set {assignments}, updated_at = ? where id = ?", (*fields.values(), now(), case_id))


# check ins, events and the audit log


def save_checkin(user_hash, phq4, safety_yes):
    with tx() as c:
        c.execute(
            "insert into checkins (user_hash, phq4, safety_yes, created_at) values (?, ?, ?, ?)",
            (user_hash, phq4, int(safety_yes), now()),
        )


def log_event(c, kind, tier=None, channel=None):
    # anonymous counts for sponsors, never linked to a person
    c.execute("insert into events (kind, tier, channel, created_at) values (?, ?, ?, ?)", (kind, tier, channel, now()))


def record_event(kind, tier=None, channel=None):
    with tx() as c:
        log_event(c, kind, tier, channel)


def audit(actor, action, case_id=None):
    with tx() as c:
        c.execute(
            "insert into audit_log (actor, action, case_id, created_at) values (?, ?, ?, ?)",
            (actor, action, case_id, now()),
        )


def purge_expired(retention_days):
    # delete messages, check ins and closed cases older than the retention window
    cutoff = _since(timedelta(days=retention_days))
    with tx() as c:
        n = c.execute("delete from messages where created_at < ?", (cutoff,)).rowcount
        c.execute("delete from cases where status = 'closed' and updated_at < ?", (cutoff,))
        c.execute("delete from checkins where created_at < ?", (cutoff,))
    return n


def stats(days=30):
    cutoff = _since(timedelta(days=days))
    with tx() as c:
        rows = c.execute(
            "select kind, coalesce(tier, '-') as tier, coalesce(channel, '-') as channel, count(*) as n "
            "from events where created_at >= ? group by kind, tier, channel order by kind",
            (cutoff,),
        ).fetchall()
        open_cases = c.execute("select tier, count(*) from cases where status != 'closed' group by tier").fetchall()
    return {
        "window_days": days,
        "events": [dict(r) for r in rows],
        "open_cases": {r[0]: r[1] for r in open_cases},
    }
