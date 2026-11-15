"""SQLite 读写层。

原则：这里只做增删查，绝不调用模型，也不写业务判断。
"""
import json
import os
import random
import sqlite3
import time
import uuid

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS rooms (
    id         TEXT PRIMARY KEY,
    code       TEXT UNIQUE NOT NULL,
    topic      TEXT,
    status     TEXT DEFAULT 'discussing',
    created_at REAL
);

CREATE TABLE IF NOT EXISTS members (
    id        TEXT PRIMARY KEY,
    room_id   TEXT,
    name      TEXT,
    color     TEXT,
    joined_at REAL
);

CREATE TABLE IF NOT EXISTS messages (
    id          TEXT PRIMARY KEY,
    room_id     TEXT,
    member_id   TEXT,
    role        TEXT,
    content     TEXT,
    duration_ms INTEGER DEFAULT 0,
    created_at  REAL
);

CREATE TABLE IF NOT EXISTS cards (
    id         TEXT PRIMARY KEY,
    room_id    TEXT,
    message_id TEXT,
    kind       TEXT,
    content    TEXT,
    confidence REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS minutes (
    id         TEXT PRIMARY KEY,
    room_id    TEXT,
    data       TEXT,
    created_at REAL
);
"""


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


# ---------------- 房间 ----------------

def create_room(topic: str) -> dict:
    conn = _conn()
    code = ""
    for _ in range(50):
        candidate = f"{random.randint(1000, 9999)}"
        if not conn.execute("SELECT 1 FROM rooms WHERE code=?", (candidate,)).fetchone():
            code = candidate
            break
    if not code:
        code = str(int(time.time()))[-4:]

    room_id = new_id("rm_")
    conn.execute(
        "INSERT INTO rooms (id, code, topic, status, created_at) VALUES (?,?,?,?,?)",
        (room_id, code, topic, "discussing", time.time()),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM rooms WHERE id=?", (room_id,)).fetchone()
    conn.close()
    return dict(row)


def get_room_by_code(code: str):
    conn = _conn()
    row = conn.execute("SELECT * FROM rooms WHERE code=?", (code,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_room(room_id: str):
    conn = _conn()
    row = conn.execute("SELECT * FROM rooms WHERE id=?", (room_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def set_status(room_id: str, status: str) -> None:
    conn = _conn()
    conn.execute("UPDATE rooms SET status=? WHERE id=?", (status, room_id))
    conn.commit()
    conn.close()


# ---------------- 成员 ----------------

def add_member(room_id: str, name: str, color: str) -> dict:
    conn = _conn()
    mid = new_id("mb_")
    conn.execute(
        "INSERT INTO members (id, room_id, name, color, joined_at) VALUES (?,?,?,?,?)",
        (mid, room_id, name, color, time.time()),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM members WHERE id=?", (mid,)).fetchone()
    conn.close()
    return dict(row)


def list_members(room_id: str) -> list:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM members WHERE room_id=? ORDER BY joined_at", (room_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------- 消息 ----------------

def add_message(room_id: str, member_id: str, role: str,
                content: str, duration_ms: int = 0) -> dict:
    conn = _conn()
    mid = new_id("ms_")
    now = time.time()
    conn.execute(
        "INSERT INTO messages (id, room_id, member_id, role, content, duration_ms, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (mid, room_id, member_id, role, content, duration_ms, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
    conn.close()
    return dict(row)


def list_messages(room_id: str, limit: int = 300) -> list:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM messages WHERE room_id=? ORDER BY created_at LIMIT ?",
        (room_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def sum_duration(room_id: str) -> dict:
    conn = _conn()
    rows = conn.execute(
        "SELECT member_id, SUM(duration_ms) AS ms FROM messages"
        " WHERE room_id=? AND role='user' GROUP BY member_id",
        (room_id,),
    ).fetchall()
    conn.close()
    return {r["member_id"]: r["ms"] or 0 for r in rows}


# ---------------- 卡片 ----------------

def add_card(room_id: str, message_id: str, kind: str,
             content: str, confidence: float) -> dict:
    conn = _conn()
    cid = new_id("cd_")
    conn.execute(
        "INSERT INTO cards (id, room_id, message_id, kind, content, confidence)"
        " VALUES (?,?,?,?,?,?)",
        (cid, room_id, message_id, kind, content, confidence),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
    conn.close()
    return dict(row)


def list_cards(room_id: str) -> list:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM cards WHERE room_id=? ORDER BY rowid", (room_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------- 纪要 ----------------

def save_minutes(room_id: str, data: dict) -> None:
    conn = _conn()
    conn.execute(
        "INSERT INTO minutes (id, room_id, data, created_at) VALUES (?,?,?,?)",
        (new_id("mn_"), room_id, json.dumps(data, ensure_ascii=False), time.time()),
    )
    conn.commit()
    conn.close()


def latest_minutes(room_id: str):
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM minutes WHERE room_id=? ORDER BY created_at DESC LIMIT 1",
        (room_id,),
    ).fetchone()
    conn.close()
    return json.loads(row["data"]) if row else None
