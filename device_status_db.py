"""SQLite helper for device ping status tracking."""

import sqlite3
import os
import subprocess
import platform
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "device_status.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()

    # ── Detect old schema (device_id PRIMARY KEY, no 'id' column) and migrate ─
    col_names = [row[1] for row in conn.execute("PRAGMA table_info(device_status)").fetchall()]
    if col_names and "id" not in col_names:
        # Drop stale table so CREATE below builds the correct schema
        conn.execute("DROP TABLE device_status")

    # ── Create table with composite-unique (device_id, category) schema ────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS device_status (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id     TEXT NOT NULL,
            category      TEXT NOT NULL,
            model_name    TEXT NOT NULL,
            device_name   TEXT,
            device_ip     TEXT,
            serial_number TEXT,
            status        TEXT DEFAULT 'unknown',
            last_checked  TEXT,
            UNIQUE(device_id, category)
        )
    """)
    conn.commit()
    conn.close()


def sync_devices_to_db(data):
    """
    Full sync: clears the DB, re-inserts every device from the JSON with the
    correct category key.  Previously recorded ping status / last_checked are
    preserved so historical results are not lost.
    Supports the new per-category JSON structure (Regression_devices, etc.).
    """
    from nax_config import DEVICE_CATEGORIES

    # Guarantee the table exists before any query (safe to call repeatedly)
    init_db()

    conn = get_connection()

    # ── Preserve existing ping results (empty dict on a brand-new DB) ─────────
    try:
        existing = {
            row["device_id"]: dict(row)
            for row in conn.execute(
                "SELECT device_id, status, last_checked FROM device_status"
            ).fetchall()
        }
    except Exception:
        existing = {}

    # ── Determine category sections ──────────────────────────────────────────
    cat_sections = [
        (cat_key, data[cat_key])
        for cat_key in DEVICE_CATEGORIES
        if cat_key in data
    ]
    if not cat_sections and "devices" in data:
        # Legacy fallback
        cat_sections = [("devices", data["devices"])]

    # ── Wipe stale data, then re-insert from JSON ─────────────────────────────
    conn.execute("DELETE FROM device_status")

    for cat_key, cat_devices in cat_sections:
        for model_name, devices in cat_devices.items():
            for device_id, config in devices.items():
                prev = existing.get(device_id, {})
                conn.execute("""
                    INSERT INTO device_status
                        (device_id, model_name, device_name, device_ip,
                         serial_number, status, last_checked, category)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    device_id,
                    model_name,
                    config.get("device_name", model_name),
                    config.get("device_ip", ""),
                    config.get("serial_number", ""),
                    prev.get("status", config.get("status", "unknown")),
                    prev.get("last_checked"),
                    cat_key,
                ))

    conn.commit()
    conn.close()


def ping_device(ip):
    """Ping an IP address. Returns True if reachable."""
    if not ip or not ip.strip():
        return False
    param = "-n" if platform.system().lower() == "windows" else "-c"
    timeout_param = "-w" if platform.system().lower() == "windows" else "-W"
    timeout_val = "1000" if platform.system().lower() == "windows" else "1"
    try:
        result = subprocess.run(
            ["ping", param, "1", timeout_param, timeout_val, ip.strip()],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False


def update_device_status(device_id, status):
    """Update status and last_checked for ALL category rows of a device."""
    conn = get_connection()
    conn.execute("""
        UPDATE device_status
        SET status = ?, last_checked = ?
        WHERE device_id = ?
    """, (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), device_id))
    conn.commit()
    conn.close()


def get_all_devices():
    """Return one row per unique device_id (latest category row)."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT device_id, model_name, device_name, device_ip, serial_number,
               status, last_checked, category
        FROM device_status
        GROUP BY device_id
        ORDER BY model_name, device_id
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_inactive_devices():
    """Return one row per unique inactive device_id."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT device_id, model_name, device_name, device_ip, serial_number,
               status, last_checked, category
        FROM device_status
        WHERE status = 'inactive'
        GROUP BY device_id
        ORDER BY model_name, device_id
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_devices_by_category(category):
    """Return all devices for a given category key."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT device_id, model_name, device_name, device_ip, serial_number,
               status, last_checked, category
        FROM device_status
        WHERE category = ?
        ORDER BY model_name, device_id
    """, (category,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_inactive_devices_by_category(category):
    """Return inactive devices for a given category key."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT device_id, model_name, device_name, device_ip, serial_number,
               status, last_checked, category
        FROM device_status
        WHERE status = 'inactive' AND category = ?
        ORDER BY model_name, device_id
    """, (category,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_device_status_map():
    """Return a dict mapping device_id -> status (aggregated across categories)."""
    conn = get_connection()
    # If the same device appears in multiple categories, take 'inactive' if any
    rows = conn.execute("""
        SELECT device_id,
               CASE WHEN MIN(CASE status WHEN 'active' THEN 1 ELSE 0 END) = 0
                    THEN 'inactive' ELSE 'active' END AS status
        FROM device_status
        GROUP BY device_id
    """).fetchall()
    conn.close()
    return {r["device_id"]: r["status"] for r in rows}


# Initialize DB on import
init_db()
