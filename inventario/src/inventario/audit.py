"""Trazabilidad: registro de inicios de sesion y de cambios de datos."""

from __future__ import annotations

import json
import socket
import sqlite3
from typing import Any, Optional

from .db import utc_now_iso


def log_login_attempt(
    conn: sqlite3.Connection,
    *,
    username: str,
    success: bool,
    user_id: Optional[int] = None,
) -> None:
    try:
        hostname = socket.gethostname()
    except OSError:
        hostname = None
    conn.execute(
        "INSERT INTO login_log (user_id, username, timestamp, success, hostname) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, username, utc_now_iso(), 1 if success else 0, hostname),
    )
    conn.commit()


def log_change(
    conn: sqlite3.Connection,
    *,
    user_id: Optional[int],
    username: str,
    table_name: str,
    record_id: Optional[int],
    action: str,
    old_value: Optional[dict[str, Any]] = None,
    new_value: Optional[dict[str, Any]] = None,
) -> None:
    if action not in ("INSERT", "UPDATE", "DELETE"):
        raise ValueError(f"accion de auditoria invalida: {action}")
    conn.execute(
        "INSERT INTO audit_log "
        "(user_id, username, timestamp, table_name, record_id, action, old_value, new_value) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            username,
            utc_now_iso(),
            table_name,
            record_id,
            action,
            json.dumps(old_value, ensure_ascii=False) if old_value is not None else None,
            json.dumps(new_value, ensure_ascii=False) if new_value is not None else None,
        ),
    )


def row_to_dict(row: sqlite3.Row | None) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    return dict(row)
