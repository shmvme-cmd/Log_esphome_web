"""
SQLite data layer.
Tables:
  devices          — saved device credentials (IP + API key)
  autotune_results — parsed PID autotune sessions
"""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "esphome.db"


# ───────────────────────────── connection ─────────────────────────────

@contextmanager
def _db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ───────────────────────────── schema ─────────────────────────────────

def init_db() -> None:
    with _db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                ip         TEXT    NOT NULL,
                api_key    TEXT    NOT NULL,
                created_at TEXT    DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS autotune_results (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id   INTEGER REFERENCES devices(id) ON DELETE SET NULL,
                device_ip   TEXT    NOT NULL,
                device_name TEXT,
                started_at  TEXT    NOT NULL,
                status      TEXT,
                raw_text    TEXT    NOT NULL,
                kp          REAL,
                ki          REAL,
                kd          REAL,
                rules_json  TEXT,
                saved_at    TEXT    DEFAULT (datetime('now','localtime'))
            );
            """
        )


# ───────────────────────────── devices ────────────────────────────────

def devices_list() -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, name, ip, created_at FROM devices ORDER BY name COLLATE NOCASE"
        ).fetchall()
        return [dict(r) for r in rows]


def device_get(device_id: int) -> dict | None:
    with _db() as conn:
        row = conn.execute(
            "SELECT id, name, ip, api_key, created_at FROM devices WHERE id=?",
            (device_id,),
        ).fetchone()
        return dict(row) if row else None


def device_by_ip(ip: str) -> dict | None:
    """Return the most recently created device with a given IP, if any."""
    with _db() as conn:
        row = conn.execute(
            "SELECT id, name, ip FROM devices WHERE ip=? ORDER BY id DESC LIMIT 1",
            (ip,),
        ).fetchone()
        return dict(row) if row else None


def device_save(name: str, ip: str, api_key: str) -> int:
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO devices (name, ip, api_key) VALUES (?,?,?)",
            (name.strip(), ip.strip(), api_key.strip()),
        )
        return cur.lastrowid


def device_delete(device_id: int) -> bool:
    with _db() as conn:
        cur = conn.execute("DELETE FROM devices WHERE id=?", (device_id,))
        return cur.rowcount > 0


# ───────────────────────────── result parsing ─────────────────────────

def parse_pid_result(raw_text: str) -> dict:
    """
    Extract status, main kp/ki/kd and alternative rules from autotune log text.
    """
    info: dict = {
        "status": None,
        "kp": None,
        "ki": None,
        "kd": None,
        "rules": [],
        "device_name": None,
    }

    # Status line: "State: Succeeded!"
    m = re.search(r"State:\s*(.+)", raw_text)
    if m:
        info["status"] = m.group(1).strip().rstrip("!").strip()

    # Main PID params block (multi-line, possible leading spaces)
    m = re.search(
        r"control_parameters:\s*\n\s*kp:\s*([\d.]+)\s*\n\s*ki:\s*([\d.]+)\s*\n\s*kd:\s*([\d.]+)",
        raw_text,
    )
    if m:
        info["kp"] = float(m.group(1))
        info["ki"] = float(m.group(2))
        info["kd"] = float(m.group(3))

    # Alternative rules: "Rule 'Name':\nkp: X, ki: Y, kd: Z"
    rules = []
    for m in re.finditer(
        r"Rule '([^']+)':\s*\n\s*kp:\s*([\d.]+),\s*ki:\s*([\d.]+),\s*kd:\s*([\d.]+)",
        raw_text,
    ):
        rules.append(
            {
                "name": m.group(1),
                "kp": float(m.group(2)),
                "ki": float(m.group(3)),
                "kd": float(m.group(4)),
            }
        )
    info["rules"] = rules

    # Device name from "xxx: Autotune completed"
    m = re.search(r"^(.+?):\s*Autotune completed", raw_text, re.MULTILINE)
    if m:
        info["device_name"] = m.group(1).strip()

    return info


# ───────────────────────────── results ────────────────────────────────

def result_save(device_ip: str, started_at: str, raw_text: str,
                device_id: int | None = None) -> int:
    parsed = parse_pid_result(raw_text)
    with _db() as conn:
        cur = conn.execute(
            """
            INSERT INTO autotune_results
                (device_id, device_ip, device_name, started_at,
                 status, raw_text, kp, ki, kd, rules_json)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                device_id,
                device_ip,
                parsed["device_name"],
                started_at,
                parsed["status"],
                raw_text,
                parsed["kp"],
                parsed["ki"],
                parsed["kd"],
                json.dumps(parsed["rules"], ensure_ascii=False),
            ),
        )
        return cur.lastrowid


def results_list(device_ip: str | None = None, device_id: int | None = None) -> list[dict]:
    query = """
        SELECT  r.id, r.device_ip, r.device_name, r.started_at, r.saved_at,
                r.status, r.kp, r.ki, r.kd, r.device_id,
                d.name AS saved_device_name
        FROM    autotune_results r
        LEFT JOIN devices d ON d.id = r.device_id
    """
    params: list = []
    if device_id is not None:
        query += " WHERE r.device_id = ?"
        params.append(device_id)
    elif device_ip:
        query += " WHERE r.device_ip = ?"
        params.append(device_ip)
    query += " ORDER BY r.saved_at DESC"
    with _db() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def result_get(result_id: int) -> dict | None:
    with _db() as conn:
        row = conn.execute(
            """
            SELECT r.*, d.name AS saved_device_name
            FROM   autotune_results r
            LEFT JOIN devices d ON d.id = r.device_id
            WHERE  r.id = ?
            """,
            (result_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["rules"] = json.loads(d.get("rules_json") or "[]")
        return d


def result_delete(result_id: int) -> bool:
    with _db() as conn:
        cur = conn.execute("DELETE FROM autotune_results WHERE id=?", (result_id,))
        return cur.rowcount > 0


def results_ips() -> list[str]:
    """All distinct device IPs that have results."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT device_ip FROM autotune_results ORDER BY device_ip"
        ).fetchall()
        return [r["device_ip"] for r in rows]
