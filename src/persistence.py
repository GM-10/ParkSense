"""SQLite persistence layer for ParkSense — replaces all in-memory state."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_DB_PATH = Path(__file__).resolve().parent.parent / "db" / "parksense.db"
_LOCAL = threading.local()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db() -> sqlite3.Connection:
    """Thread-local SQLite connection with WAL mode."""
    conn = getattr(_LOCAL, "conn", None)
    if conn is None:
        os.makedirs(_DB_PATH.parent, exist_ok=True)
        conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        _LOCAL.conn = conn
    return conn


def init_db() -> None:
    """Create all tables and seed demo users if not present."""
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('Admin','Supervisor','Field Officer','Analyst')),
            jurisdiction TEXT DEFAULT 'Bengaluru',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            revoked INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS resolved_alerts (
            alert_id TEXT PRIMARY KEY,
            resolved_by TEXT,
            resolved_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alert_states (
            alert_id TEXT PRIMARY KEY,
            state TEXT NOT NULL CHECK (state IN ('New','Acknowledged','Assigned','Resolved','Archived')),
            updated_by TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            locality_name TEXT NOT NULL,
            incident_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            injected_by TEXT,
            injected_at TEXT NOT NULL,
            cleared INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            details TEXT
        );

        CREATE TABLE IF NOT EXISTS dispatch_log (
            id TEXT PRIMARY KEY,
            hotspot_id TEXT NOT NULL,
            hotspot_name TEXT NOT NULL,
            channel TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'en',
            payload TEXT NOT NULL,
            delivery_status TEXT NOT NULL DEFAULT 'pending',
            sent_by TEXT,
            sent_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS officer_feedback (
            id TEXT PRIMARY KEY,
            hotspot_id TEXT NOT NULL,
            hotspot_name TEXT NOT NULL,
            feedback_text TEXT NOT NULL,
            submitted_by TEXT,
            submitted_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ingested_violations (
            id TEXT PRIMARY KEY,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            violation_type TEXT NOT NULL DEFAULT 'WRONG PARKING',
            vehicle_type TEXT DEFAULT 'UNKNOWN',
            severity REAL DEFAULT 2.0,
            location_label TEXT,
            junction_name TEXT,
            police_station TEXT,
            occurred_at TEXT NOT NULL,
            ingested_at TEXT NOT NULL,
            ingested_by TEXT
        );

        CREATE TABLE IF NOT EXISTS fleet_resources (
            resource_type TEXT PRIMARY KEY,
            total_count INTEGER NOT NULL,
            available_count INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS dispatch_deployments (
            id TEXT PRIMARY KEY,
            hotspot_id TEXT NOT NULL,
            hotspot_name TEXT NOT NULL,
            risk_score REAL NOT NULL,
            current_violations INTEGER NOT NULL,
            predicted_violations_next_hour INTEGER NOT NULL,
            severity TEXT NOT NULL,
            recommended_officers INTEGER NOT NULL,
            recommended_patrol_vehicles INTEGER NOT NULL,
            assigned_officers INTEGER NOT NULL DEFAULT 0,
            assigned_vehicles INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Assigned',
            priority_score REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            assigned_by TEXT,
            notes TEXT,
            timeline TEXT NOT NULL DEFAULT '2024-04'
        );

        CREATE TABLE IF NOT EXISTS dispatch_assignments (
            id TEXT PRIMARY KEY,
            deployment_id TEXT NOT NULL,
            hotspot_id TEXT NOT NULL,
            officers INTEGER NOT NULL,
            patrol_vehicles INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            created_by TEXT
        );

        CREATE TABLE IF NOT EXISTS officers_list (
            id TEXT PRIMARY KEY,
            team_name TEXT NOT NULL,
            total_strength INTEGER NOT NULL,
            available INTEGER NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('Available', 'On Duty', 'Off Shift', 'On Leave')),
            timeline TEXT NOT NULL DEFAULT '2024-04',
            UNIQUE(team_name, timeline)
        );

        CREATE TABLE IF NOT EXISTS vehicles_list (
            id TEXT PRIMARY KEY,
            vehicle_id TEXT NOT NULL,
            type TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('Available', 'Deployed', 'Maintenance', 'Offline')),
            assigned_to TEXT NOT NULL DEFAULT 'Unassigned',
            timeline TEXT NOT NULL DEFAULT '2024-04',
            UNIQUE(vehicle_id, timeline)
        );
    """)



    # Seed demo users if table is empty
    count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        demo_users = [
            ("admin", "admin", "Admin"),
            ("supervisor", "supervisor", "Supervisor"),
            ("officer", "officer", "Field Officer"),
            ("analyst", "analyst", "Analyst"),
        ]
        for username, password, role in demo_users:
            pw_hash = hashlib.sha256(password.encode()).hexdigest()
            db.execute(
                "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), username, pw_hash, role, _now_iso()),
            )
        db.commit()

    fleet_count = db.execute("SELECT COUNT(*) FROM fleet_resources").fetchone()[0]
    if fleet_count == 0:
        defaults = {
            "team": int(os.getenv("PARKSENSE_DISPATCH_TEAMS", "6")),
            "tow_vehicle": int(os.getenv("PARKSENSE_TOW_VEHICLES", "3")),
        }
        for resource_type, total_count in defaults.items():
            available_count = max(0, total_count - 1 if resource_type == "team" else total_count)
            db.execute(
                "INSERT INTO fleet_resources (resource_type, total_count, available_count, updated_at) VALUES (?, ?, ?, ?)",
                (resource_type, total_count, available_count, _now_iso()),
            )
        db.commit()

    officers_count = db.execute("SELECT COUNT(*) FROM officers_list").fetchone()[0]
    if officers_count == 0:
        db.execute("INSERT OR IGNORE INTO officers_list (id, team_name, total_strength, available, status, timeline) VALUES ('team-1', 'Alpha Team', 4, 4, 'Available', '2024-04')")
        db.execute("INSERT OR IGNORE INTO officers_list (id, team_name, total_strength, available, status, timeline) VALUES ('team-2', 'Bravo Team', 2, 2, 'Available', '2024-04')")
        db.commit()

    vehicles_count = db.execute("SELECT COUNT(*) FROM vehicles_list").fetchone()[0]
    if vehicles_count == 0:
        db.execute("INSERT OR IGNORE INTO vehicles_list (id, vehicle_id, type, status, assigned_to, timeline) VALUES ('veh-1', 'V-01', 'Patrol', 'Available', 'Unassigned', '2024-04')")
        db.execute("INSERT OR IGNORE INTO vehicles_list (id, vehicle_id, type, status, assigned_to, timeline) VALUES ('veh-2', 'V-02', 'Response', 'Available', 'Unassigned', '2024-04')")
        db.commit()

    try:
        db.execute("ALTER TABLE dispatch_deployments ADD COLUMN timeline TEXT NOT NULL DEFAULT '2024-04'")
        db.commit()
    except sqlite3.OperationalError:
        pass

    print(f"ParkSense DB initialized at {_DB_PATH}")


# ── User helpers ──────────────────────────────────────────────────────────────

def authenticate_user(username: str, password: str) -> Optional[dict]:
    db = get_db()
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    row = db.execute(
        "SELECT id, username, role FROM users WHERE username = ? AND password_hash = ?",
        (username, pw_hash),
    ).fetchone()
    if row:
        return {"id": row["id"], "username": row["username"], "role": row["role"]}
    return None


def create_session(username: str, role: str) -> str:
    db = get_db()
    token = uuid.uuid4().hex + uuid.uuid4().hex
    db.execute(
        "INSERT INTO sessions (token, username, role, created_at) VALUES (?, ?, ?, ?)",
        (token, username, role, _now_iso()),
    )
    db.commit()
    return token


def validate_session(token: str) -> Optional[dict]:
    db = get_db()
    row = db.execute(
        "SELECT username, role FROM sessions WHERE token = ? AND revoked = 0", (token,)
    ).fetchone()
    if row:
        return {"username": row["username"], "role": row["role"]}
    return None


def revoke_session(token: str) -> None:
    db = get_db()
    db.execute("UPDATE sessions SET revoked = 1 WHERE token = ?", (token,))
    db.commit()


# ── Alert helpers ─────────────────────────────────────────────────────────────

def is_alert_resolved(alert_id: str) -> bool:
    db = get_db()
    row = db.execute(
        "SELECT 1 FROM alert_states WHERE alert_id = ? AND state IN ('Resolved', 'Archived')",
        (alert_id,)
    ).fetchone()
    if row is not None:
        return True
    row = db.execute("SELECT 1 FROM resolved_alerts WHERE alert_id = ?", (alert_id,)).fetchone()
    return row is not None


def get_alert_states() -> dict[str, str]:
    db = get_db()
    rows = db.execute("SELECT alert_id, state FROM alert_states").fetchall()
    return {r["alert_id"]: r["state"] for r in rows}


def update_alert_state(alert_id: str, state: str, username: str = "system") -> None:
    db = get_db()
    db.execute(
        """
        INSERT INTO alert_states (alert_id, state, updated_by, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(alert_id) DO UPDATE SET
            state = excluded.state,
            updated_by = excluded.updated_by,
            updated_at = excluded.updated_at
        """,
        (alert_id, state, username, _now_iso()),
    )
    if state in ("Resolved", "Archived"):
        db.execute(
            "INSERT OR IGNORE INTO resolved_alerts (alert_id, resolved_by, resolved_at) VALUES (?, ?, ?)",
            (alert_id, username, _now_iso()),
        )
    db.commit()


def resolve_alert(alert_id: str, username: str = "system") -> None:
    update_alert_state(alert_id, "Resolved", username)


# ── Incident helpers ──────────────────────────────────────────────────────────

def add_incident(data: dict, username: str = "system") -> str:
    db = get_db()
    inc_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO incidents (id, locality_name, incident_type, severity, duration_minutes, injected_by, injected_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (inc_id, data["locality_name"], data["incident_type"], data["severity"], data["duration_minutes"], username, _now_iso()),
    )
    db.commit()
    return inc_id


def get_active_incidents() -> list[dict]:
    db = get_db()
    rows = db.execute("SELECT * FROM incidents WHERE cleared = 0").fetchall()
    return [dict(r) for r in rows]


def clear_all_incidents(username: str = "system") -> int:
    db = get_db()
    count = db.execute("SELECT COUNT(*) FROM incidents WHERE cleared = 0").fetchone()[0]
    db.execute("UPDATE incidents SET cleared = 1")
    db.commit()
    return count


# ── Audit helpers ─────────────────────────────────────────────────────────────

def log_audit(username: str, action: str, entity_type: str = "", entity_id: str = "", details: Any = None) -> None:
    db = get_db()
    db.execute(
        "INSERT INTO audit_log (timestamp, username, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?, ?)",
        (_now_iso(), username, action, entity_type, entity_id, json.dumps(details) if details else None),
    )
    db.commit()


def get_audit_log(limit: int = 100) -> list[dict]:
    db = get_db()
    rows = db.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ── Dispatch log helpers ──────────────────────────────────────────────────────

def log_dispatch(hotspot_id: str, hotspot_name: str, channel: str, language: str, payload: str, status: str, username: str) -> str:
    db = get_db()
    dispatch_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO dispatch_log (id, hotspot_id, hotspot_name, channel, language, payload, delivery_status, sent_by, sent_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (dispatch_id, hotspot_id, hotspot_name, channel, language, payload, status, username, _now_iso()),
    )
    db.commit()
    return dispatch_id


def get_dispatch_log(limit: int = 50) -> list[dict]:
    db = get_db()
    rows = db.execute("SELECT * FROM dispatch_log ORDER BY sent_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ── Officer feedback helpers ──────────────────────────────────────────────────

def save_feedback(hotspot_id: str, hotspot_name: str, text: str, username: str) -> str:
    db = get_db()
    fb_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO officer_feedback (id, hotspot_id, hotspot_name, feedback_text, submitted_by, submitted_at) VALUES (?, ?, ?, ?, ?, ?)",
        (fb_id, hotspot_id, hotspot_name, text, username, _now_iso()),
    )
    db.commit()
    return fb_id


def get_feedback(hotspot_id: Optional[str] = None, limit: int = 50) -> list[dict]:
    db = get_db()
    if hotspot_id:
        rows = db.execute(
            "SELECT * FROM officer_feedback WHERE hotspot_id = ? ORDER BY submitted_at DESC LIMIT ?",
            (hotspot_id, limit),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM officer_feedback ORDER BY submitted_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ── Ingested violations helpers ───────────────────────────────────────────────

def ingest_violation(data: dict, username: str = "system") -> str:
    db = get_db()
    v_id = str(uuid.uuid4())
    db.execute(
        """INSERT INTO ingested_violations
        (id, latitude, longitude, violation_type, vehicle_type, severity, location_label, junction_name, police_station, occurred_at, ingested_at, ingested_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            v_id,
            data["latitude"],
            data["longitude"],
            data.get("violation_type", "WRONG PARKING"),
            data.get("vehicle_type", "UNKNOWN"),
            data.get("severity", 2.0),
            data.get("location_label", ""),
            data.get("junction_name", ""),
            data.get("police_station", ""),
            data.get("occurred_at", _now_iso()),
            _now_iso(),
            username,
        ),
    )
    db.commit()
    return v_id


def get_ingested_violations() -> list[dict]:
    db = get_db()
    rows = db.execute("SELECT * FROM ingested_violations ORDER BY ingested_at DESC").fetchall()
    return [dict(r) for r in rows]


def count_ingested_violations() -> int:
    db = get_db()
    return db.execute("SELECT COUNT(*) FROM ingested_violations").fetchone()[0]


def get_fleet_resources() -> list[dict]:
    db = get_db()
    rows = db.execute("SELECT * FROM fleet_resources ORDER BY resource_type").fetchall()
    return [dict(r) for r in rows]


def update_fleet_resource(resource_type: str, total_count: int, available_count: int) -> None:
    db = get_db()
    db.execute(
        """
        INSERT INTO fleet_resources (resource_type, total_count, available_count, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(resource_type) DO UPDATE SET
            total_count = excluded.total_count,
            available_count = excluded.available_count,
            updated_at = excluded.updated_at
        """,
        (resource_type, total_count, available_count, _now_iso()),
    )
    db.commit()


def get_dispatch_deployments(timeline: Optional[str] = None) -> list[dict]:
    db = get_db()
    if timeline:
        rows = db.execute("SELECT * FROM dispatch_deployments WHERE timeline = ? ORDER BY priority_score DESC, created_at DESC", (timeline,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM dispatch_deployments ORDER BY priority_score DESC, created_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_dispatch_deployment(deployment_id: str) -> Optional[dict]:
    db = get_db()
    row = db.execute("SELECT * FROM dispatch_deployments WHERE id = ?", (deployment_id,)).fetchone()
    return dict(row) if row else None


def create_dispatch_deployment(data: dict, username: str = "system") -> str:
    db = get_db()
    dep_id = str(uuid.uuid4())
    now = _now_iso()
    db.execute(
        """INSERT INTO dispatch_deployments
        (id, hotspot_id, hotspot_name, risk_score, current_violations, predicted_violations_next_hour, severity,
         recommended_officers, recommended_patrol_vehicles, assigned_officers, assigned_vehicles, status,
         priority_score, created_at, updated_at, assigned_by, notes, timeline)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            dep_id,
            data["hotspot_id"],
            data["hotspot_name"],
            data["risk_score"],
            data["current_violations"],
            data["predicted_violations_next_hour"],
            data["severity"],
            data["recommended_officers"],
            data["recommended_patrol_vehicles"],
            data.get("assigned_officers", 0),
            data.get("assigned_vehicles", 0),
            data.get("status", "Assigned"),
            data["priority_score"],
            now,
            now,
            username,
            data.get("notes"),
            data.get("timeline", "2024-04"),
        ),
    )
    db.commit()
    return dep_id


def update_dispatch_deployment(deployment_id: str, **fields: Any) -> None:
    if not fields:
        return
    db = get_db()
    fields = dict(fields)
    fields["updated_at"] = _now_iso()
    assignments = ", ".join([f"{key} = ?" for key in fields.keys()])
    values = list(fields.values()) + [deployment_id]
    db.execute(f"UPDATE dispatch_deployments SET {assignments} WHERE id = ?", values)
    db.commit()


def add_dispatch_assignment(deployment_id: str, hotspot_id: str, officers: int, patrol_vehicles: int, username: str = "system") -> str:
    db = get_db()
    assignment_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO dispatch_assignments (id, deployment_id, hotspot_id, officers, patrol_vehicles, created_at, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (assignment_id, deployment_id, hotspot_id, officers, patrol_vehicles, _now_iso(), username),
    )
    db.commit()
    return assignment_id


def get_dispatch_assignments() -> list[dict]:
    db = get_db()
    rows = db.execute("SELECT * FROM dispatch_assignments ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


# ── Officer CRUD helpers ──────────────────────────────────────────────────────
def get_officers(timeline: Optional[str] = "2024-04") -> list[dict]:
    db = get_db()
    if not timeline:
        timeline = "2024-04"
    count = db.execute("SELECT COUNT(*) FROM officers_list WHERE timeline = ?", (timeline,)).fetchone()[0]
    if count == 0:
        db.execute("INSERT OR IGNORE INTO officers_list (id, team_name, total_strength, available, status, timeline) VALUES ('team-1-' || ?, 'Alpha Team', 4, 4, 'Available', ?)", (timeline, timeline))
        db.execute("INSERT OR IGNORE INTO officers_list (id, team_name, total_strength, available, status, timeline) VALUES ('team-2-' || ?, 'Bravo Team', 2, 2, 'Available', ?)", (timeline, timeline))
        db.commit()
    rows = db.execute("SELECT * FROM officers_list WHERE timeline = ?", (timeline,)).fetchall()
    return [dict(r) for r in rows]

def create_officer_team(team_name: str, total_strength: int, available: int, status: str, timeline: Optional[str] = "2024-04") -> str:
    db = get_db()
    if not timeline:
        timeline = "2024-04"
    team_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO officers_list (id, team_name, total_strength, available, status, timeline) VALUES (?, ?, ?, ?, ?, ?)",
        (team_id, team_name, total_strength, available, status, timeline),
    )
    db.commit()
    return team_id

def update_officer_team(team_id: str, team_name: str, total_strength: int, available: int, status: str) -> None:
    db = get_db()
    db.execute(
        "UPDATE officers_list SET team_name = ?, total_strength = ?, available = ?, status = ? WHERE id = ?",
        (team_name, total_strength, available, status, team_id),
    )
    db.commit()

def delete_officer_team(team_id: str) -> None:
    db = get_db()
    db.execute("DELETE FROM officers_list WHERE id = ?", (team_id,))
    db.commit()

# ── Vehicle CRUD helpers ──────────────────────────────────────────────────────
def get_vehicles(timeline: Optional[str] = "2024-04") -> list[dict]:
    db = get_db()
    if not timeline:
        timeline = "2024-04"
    count = db.execute("SELECT COUNT(*) FROM vehicles_list WHERE timeline = ?", (timeline,)).fetchone()[0]
    if count == 0:
        db.execute("INSERT OR IGNORE INTO vehicles_list (id, vehicle_id, type, status, assigned_to, timeline) VALUES ('veh-1-' || ?, 'V-01', 'Patrol', 'Available', 'Unassigned', ?)", (timeline, timeline))
        db.execute("INSERT OR IGNORE INTO vehicles_list (id, vehicle_id, type, status, assigned_to, timeline) VALUES ('veh-2-' || ?, 'V-02', 'Response', 'Available', 'Unassigned', ?)", (timeline, timeline))
        db.commit()
    rows = db.execute("SELECT * FROM vehicles_list WHERE timeline = ?", (timeline,)).fetchall()
    return [dict(r) for r in rows]

def create_vehicle(vehicle_id: str, type: str, status: str, assigned_to: str, timeline: Optional[str] = "2024-04") -> str:
    db = get_db()
    if not timeline:
        timeline = "2024-04"
    id_val = str(uuid.uuid4())
    db.execute(
        "INSERT INTO vehicles_list (id, vehicle_id, type, status, assigned_to, timeline) VALUES (?, ?, ?, ?, ?, ?)",
        (id_val, vehicle_id, type, status, assigned_to, timeline),
    )
    db.commit()
    return id_val

def update_vehicle(id_val: str, vehicle_id: str, type: str, status: str, assigned_to: str) -> None:
    db = get_db()
    db.execute(
        "UPDATE vehicles_list SET vehicle_id = ?, type = ?, status = ?, assigned_to = ? WHERE id = ?",
        (vehicle_id, type, status, assigned_to, id_val),
    )
    db.commit()

def delete_vehicle(id_val: str) -> None:
    db = get_db()
    db.execute("DELETE FROM vehicles_list WHERE id = ?", (id_val,))
    db.commit()
