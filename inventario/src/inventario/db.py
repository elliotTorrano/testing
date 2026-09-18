"""Capa de datos: apertura/cierre de la base de datos cifrada y esquema SQL.

La base de datos vive cifrada en disco (`inventario.db.enc`). Al abrir la
aplicacion se descifra a un archivo temporal sobre el que trabaja sqlite3;
cada operacion de escritura relevante llama a `persist()` para volver a
cifrar y sobrescribir el archivo real de forma atomica. Al cerrar la
aplicacion se persiste una ultima vez y se borra el archivo temporal.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import datetime, timezone

from . import security

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('administrador', 'capturista')),
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    image_path TEXT,
    sale_price REAL NOT NULL DEFAULT 0,
    avg_cost REAL NOT NULL DEFAULT 0,
    stock REAL NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    type TEXT NOT NULL CHECK (type IN ('compra', 'venta', 'ajuste')),
    quantity REAL NOT NULL,
    unit_cost REAL NOT NULL,
    unit_price REAL,
    total REAL,
    expected_profit REAL,
    date TEXT NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id),
    note TEXT
);

CREATE TABLE login_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    success INTEGER NOT NULL,
    hostname TEXT
);

CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    table_name TEXT NOT NULL,
    record_id INTEGER,
    action TEXT NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    old_value TEXT,
    new_value TEXT
);
"""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    """Envuelve una conexion sqlite3 respaldada por un archivo cifrado."""

    def __init__(self, enc_path: str, key_path: str):
        self.enc_path = enc_path
        self.key_path = key_path
        self.key = security.load_or_create_key(key_path)
        self.is_new = not os.path.exists(enc_path)

        fd, self._tmp_path = tempfile.mkstemp(suffix=".sqlite3", prefix="inventario_")
        os.close(fd)

        if not self.is_new:
            with open(enc_path, "rb") as f:
                token = f.read()
            plain = security.decrypt_bytes(token, self.key)
            with open(self._tmp_path, "wb") as f:
                f.write(plain)

        self.conn = sqlite3.connect(self._tmp_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

        if self.is_new:
            self.conn.executescript(SCHEMA_SQL)
            self.conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            self.conn.commit()
            self.persist()

    def persist(self) -> None:
        """Vuelca los cambios a disco y re-cifra el archivo real (reemplazo atomico)."""
        self.conn.commit()
        with open(self._tmp_path, "rb") as f:
            plain = f.read()
        token = security.encrypt_bytes(plain, self.key)
        tmp_enc_path = self.enc_path + ".tmp"
        os.makedirs(os.path.dirname(self.enc_path) or ".", exist_ok=True)
        with open(tmp_enc_path, "wb") as f:
            f.write(token)
        os.replace(tmp_enc_path, self.enc_path)

    def close(self) -> None:
        try:
            self.persist()
        finally:
            self.conn.close()
            try:
                os.remove(self._tmp_path)
            except OSError:
                pass

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
