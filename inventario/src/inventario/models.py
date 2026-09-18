"""Reglas de negocio: usuarios/roles, productos y movimientos de inventario.

El costeo usa el metodo de costo promedio ponderado (CPP):
  - En cada COMPRA se recalcula el costo promedio del producto:
        nuevo_promedio = (stock_actual * promedio_actual + cantidad * costo_unitario)
                          / (stock_actual + cantidad)
  - En cada VENTA el costo de venta es el promedio vigente en ese momento
    (no cambia el promedio, solo reduce el stock).
  - Los AJUSTES (conteo fisico) solo corrigen el stock, nunca el promedio.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Optional

from . import audit, security
from .db import utc_now_iso

ADMIN = "administrador"
CAPTURISTA = "capturista"
ROLES = (ADMIN, CAPTURISTA)


class AuthError(Exception):
    """Credenciales invalidas o usuario inactivo."""


class InsufficientStockError(Exception):
    """No hay existencia suficiente para la venta solicitada."""


class DuplicateSKUError(Exception):
    """Ya existe un producto con ese SKU."""


class NotFoundError(Exception):
    """El registro solicitado no existe."""


@dataclass(frozen=True)
class Session:
    """Usuario autenticado en la sesion actual (el 'actor' de la auditoria)."""

    id: int
    username: str
    full_name: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == ADMIN


# --- Usuarios --------------------------------------------------------------


def create_user(
    conn: sqlite3.Connection,
    *,
    actor: Optional[Session],
    username: str,
    full_name: str,
    password: str,
    role: str,
) -> int:
    if role not in ROLES:
        raise ValueError(f"Rol invalido: {role}")
    if not username.strip() or not full_name.strip():
        raise ValueError("El usuario y el nombre completo son obligatorios.")
    security.validate_password_policy(password)

    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing is not None:
        raise ValueError(f"Ya existe un usuario con el nombre '{username}'.")

    password_hash, password_salt = security.hash_password(password)
    created_at = utc_now_iso()
    cur = conn.execute(
        "INSERT INTO users (username, full_name, password_hash, password_salt, role, active, created_at) "
        "VALUES (?, ?, ?, ?, ?, 1, ?)",
        (username, full_name, password_hash, password_salt, role, created_at),
    )
    user_id = cur.lastrowid
    audit.log_change(
        conn,
        user_id=actor.id if actor else None,
        username=actor.username if actor else "sistema",
        table_name="users",
        record_id=user_id,
        action="INSERT",
        new_value={"username": username, "full_name": full_name, "role": role},
    )
    conn.commit()
    return user_id


def authenticate(conn: sqlite3.Connection, *, username: str, password: str) -> Session:
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    success = bool(
        row
        and row["active"]
        and security.verify_password(password, row["password_hash"], row["password_salt"])
    )
    audit.log_login_attempt(
        conn,
        username=username,
        success=success,
        user_id=row["id"] if row else None,
    )
    conn.commit()
    if not success:
        raise AuthError("Usuario o contrasena incorrectos, o usuario inactivo.")
    return Session(id=row["id"], username=row["username"], full_name=row["full_name"], role=row["role"])


def change_password(conn: sqlite3.Connection, *, actor: Session, user_id: int, new_password: str) -> None:
    security.validate_password_policy(new_password)
    row = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise NotFoundError("Usuario no encontrado.")
    password_hash, password_salt = security.hash_password(new_password)
    conn.execute(
        "UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?",
        (password_hash, password_salt, user_id),
    )
    audit.log_change(
        conn,
        user_id=actor.id,
        username=actor.username,
        table_name="users",
        record_id=user_id,
        action="UPDATE",
        old_value={"password": "***"},
        new_value={"password": "***"},
    )
    conn.commit()


def set_user_active(conn: sqlite3.Connection, *, actor: Session, user_id: int, active: bool) -> None:
    row = conn.execute("SELECT id, active FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise NotFoundError("Usuario no encontrado.")
    conn.execute("UPDATE users SET active = ? WHERE id = ?", (1 if active else 0, user_id))
    audit.log_change(
        conn,
        user_id=actor.id,
        username=actor.username,
        table_name="users",
        record_id=user_id,
        action="UPDATE",
        old_value={"active": bool(row["active"])},
        new_value={"active": active},
    )
    conn.commit()


def list_users(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, username, full_name, role, active, created_at FROM users ORDER BY username"
    ).fetchall()
    return [dict(r) for r in rows]


# --- Productos ---------------------------------------------------------


def create_product(
    conn: sqlite3.Connection,
    *,
    actor: Session,
    sku: str,
    name: str,
    sale_price: float,
    image_path: Optional[str] = None,
) -> int:
    if not sku.strip() or not name.strip():
        raise ValueError("El SKU y el nombre son obligatorios.")
    if sale_price < 0:
        raise ValueError("El precio de venta no puede ser negativo.")
    existing = conn.execute("SELECT id FROM products WHERE sku = ?", (sku,)).fetchone()
    if existing is not None:
        raise DuplicateSKUError(f"Ya existe un producto con el SKU '{sku}'.")

    now = utc_now_iso()
    cur = conn.execute(
        "INSERT INTO products (sku, name, image_path, sale_price, avg_cost, stock, active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 0, 0, 1, ?, ?)",
        (sku, name, image_path, sale_price, now, now),
    )
    product_id = cur.lastrowid
    audit.log_change(
        conn,
        user_id=actor.id,
        username=actor.username,
        table_name="products",
        record_id=product_id,
        action="INSERT",
        new_value={"sku": sku, "name": name, "sale_price": sale_price},
    )
    conn.commit()
    return product_id


def update_product(
    conn: sqlite3.Connection,
    *,
    actor: Session,
    product_id: int,
    name: Optional[str] = None,
    sale_price: Optional[float] = None,
    image_path: Optional[str] = None,
) -> None:
    product = get_product(conn, product_id)
    old_value = {"name": product["name"], "sale_price": product["sale_price"], "image_path": product["image_path"]}

    new_name = product["name"] if name is None else name
    new_sale_price = product["sale_price"] if sale_price is None else sale_price
    new_image_path = product["image_path"] if image_path is None else image_path
    if new_sale_price < 0:
        raise ValueError("El precio de venta no puede ser negativo.")

    conn.execute(
        "UPDATE products SET name = ?, sale_price = ?, image_path = ?, updated_at = ? WHERE id = ?",
        (new_name, new_sale_price, new_image_path, utc_now_iso(), product_id),
    )
    audit.log_change(
        conn,
        user_id=actor.id,
        username=actor.username,
        table_name="products",
        record_id=product_id,
        action="UPDATE",
        old_value=old_value,
        new_value={"name": new_name, "sale_price": new_sale_price, "image_path": new_image_path},
    )
    conn.commit()


def set_product_active(conn: sqlite3.Connection, *, actor: Session, product_id: int, active: bool) -> None:
    product = get_product(conn, product_id)
    conn.execute("UPDATE products SET active = ?, updated_at = ? WHERE id = ?", (1 if active else 0, utc_now_iso(), product_id))
    audit.log_change(
        conn,
        user_id=actor.id,
        username=actor.username,
        table_name="products",
        record_id=product_id,
        action="UPDATE",
        old_value={"active": bool(product["active"])},
        new_value={"active": active},
    )
    conn.commit()


def get_product(conn: sqlite3.Connection, product_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"Producto {product_id} no encontrado.")
    return row


def list_products(conn: sqlite3.Connection, *, only_active: bool = True) -> list[sqlite3.Row]:
    if only_active:
        return conn.execute("SELECT * FROM products WHERE active = 1 ORDER BY name").fetchall()
    return conn.execute("SELECT * FROM products ORDER BY name").fetchall()


# --- Movimientos (costo promedio ponderado) -----------------------------


def register_purchase(
    conn: sqlite3.Connection,
    *,
    actor: Session,
    product_id: int,
    quantity: float,
    unit_cost: float,
    date: Optional[str] = None,
    note: Optional[str] = None,
) -> int:
    if quantity <= 0:
        raise ValueError("La cantidad comprada debe ser mayor a cero.")
    if unit_cost < 0:
        raise ValueError("El costo de compra no puede ser negativo.")

    product = get_product(conn, product_id)
    old_stock, old_avg = product["stock"], product["avg_cost"]
    new_stock = old_stock + quantity
    new_avg = (old_stock * old_avg + quantity * unit_cost) / new_stock

    date = date or utc_now_iso()
    cur = conn.execute(
        "INSERT INTO movements "
        "(product_id, type, quantity, unit_cost, unit_price, total, expected_profit, date, user_id, note) "
        "VALUES (?, 'compra', ?, ?, NULL, ?, NULL, ?, ?, ?)",
        (product_id, quantity, unit_cost, quantity * unit_cost, date, actor.id, note),
    )
    movement_id = cur.lastrowid

    conn.execute(
        "UPDATE products SET stock = ?, avg_cost = ?, updated_at = ? WHERE id = ?",
        (new_stock, new_avg, utc_now_iso(), product_id),
    )
    audit.log_change(
        conn, user_id=actor.id, username=actor.username, table_name="products", record_id=product_id,
        action="UPDATE",
        old_value={"stock": old_stock, "avg_cost": old_avg},
        new_value={"stock": new_stock, "avg_cost": new_avg},
    )
    audit.log_change(
        conn, user_id=actor.id, username=actor.username, table_name="movements", record_id=movement_id,
        action="INSERT",
        new_value={"type": "compra", "product_id": product_id, "quantity": quantity, "unit_cost": unit_cost},
    )
    conn.commit()
    return movement_id


def register_sale(
    conn: sqlite3.Connection,
    *,
    actor: Session,
    product_id: int,
    quantity: float,
    unit_price: float,
    date: Optional[str] = None,
    note: Optional[str] = None,
    allow_negative_stock: bool = False,
) -> int:
    if quantity <= 0:
        raise ValueError("La cantidad vendida debe ser mayor a cero.")
    if unit_price < 0:
        raise ValueError("El precio de venta no puede ser negativo.")

    product = get_product(conn, product_id)
    if not allow_negative_stock and quantity > product["stock"]:
        raise InsufficientStockError(
            f"Stock insuficiente para '{product['name']}': disponible {product['stock']}, solicitado {quantity}."
        )

    unit_cost = product["avg_cost"]  # costo congelado al momento de la venta
    total = quantity * unit_price
    expected_profit = (unit_price - unit_cost) * quantity
    old_stock = product["stock"]
    new_stock = old_stock - quantity

    date = date or utc_now_iso()
    cur = conn.execute(
        "INSERT INTO movements "
        "(product_id, type, quantity, unit_cost, unit_price, total, expected_profit, date, user_id, note) "
        "VALUES (?, 'venta', ?, ?, ?, ?, ?, ?, ?, ?)",
        (product_id, quantity, unit_cost, unit_price, total, expected_profit, date, actor.id, note),
    )
    movement_id = cur.lastrowid

    conn.execute(
        "UPDATE products SET stock = ?, updated_at = ? WHERE id = ?",
        (new_stock, utc_now_iso(), product_id),
    )
    audit.log_change(
        conn, user_id=actor.id, username=actor.username, table_name="products", record_id=product_id,
        action="UPDATE",
        old_value={"stock": old_stock},
        new_value={"stock": new_stock},
    )
    audit.log_change(
        conn, user_id=actor.id, username=actor.username, table_name="movements", record_id=movement_id,
        action="INSERT",
        new_value={"type": "venta", "product_id": product_id, "quantity": quantity, "unit_price": unit_price},
    )
    conn.commit()
    return movement_id


def register_adjustment(
    conn: sqlite3.Connection,
    *,
    actor: Session,
    product_id: int,
    new_stock: float,
    note: str,
) -> int:
    if new_stock < 0:
        raise ValueError("El stock ajustado no puede ser negativo.")
    if not note.strip():
        raise ValueError("Todo ajuste de inventario requiere una nota que explique el motivo.")

    product = get_product(conn, product_id)
    old_stock = product["stock"]
    delta = new_stock - old_stock
    date = utc_now_iso()

    cur = conn.execute(
        "INSERT INTO movements "
        "(product_id, type, quantity, unit_cost, unit_price, total, expected_profit, date, user_id, note) "
        "VALUES (?, 'ajuste', ?, ?, NULL, NULL, NULL, ?, ?, ?)",
        (product_id, delta, product["avg_cost"], date, actor.id, note),
    )
    movement_id = cur.lastrowid

    conn.execute(
        "UPDATE products SET stock = ?, updated_at = ? WHERE id = ?",
        (new_stock, utc_now_iso(), product_id),
    )
    audit.log_change(
        conn, user_id=actor.id, username=actor.username, table_name="products", record_id=product_id,
        action="UPDATE",
        old_value={"stock": old_stock},
        new_value={"stock": new_stock},
    )
    audit.log_change(
        conn, user_id=actor.id, username=actor.username, table_name="movements", record_id=movement_id,
        action="INSERT",
        new_value={"type": "ajuste", "product_id": product_id, "delta": delta, "note": note},
    )
    conn.commit()
    return movement_id


def list_movements(conn: sqlite3.Connection, *, product_id: Optional[int] = None) -> list[sqlite3.Row]:
    if product_id is None:
        return conn.execute("SELECT * FROM movements ORDER BY date DESC, id DESC").fetchall()
    return conn.execute(
        "SELECT * FROM movements WHERE product_id = ? ORDER BY date DESC, id DESC", (product_id,)
    ).fetchall()


def product_summary(conn: sqlite3.Connection, product_id: int) -> dict[str, Any]:
    """Metricas agregadas de un producto: ventas totales, costo de ventas y utilidades."""
    product = get_product(conn, product_id)
    row = conn.execute(
        "SELECT COALESCE(SUM(total), 0) AS venta_total, "
        "COALESCE(SUM(quantity * unit_cost), 0) AS costo_ventas "
        "FROM movements WHERE product_id = ? AND type = 'venta'",
        (product_id,),
    ).fetchone()
    venta_total = row["venta_total"]
    costo_ventas = row["costo_ventas"]
    return {
        "producto": product["name"],
        "stock": product["stock"],
        "costo_promedio": product["avg_cost"],
        "precio_venta": product["sale_price"],
        "venta_total": venta_total,
        "costo_ventas": costo_ventas,
        "utilidad_real": venta_total - costo_ventas,
        "utilidad_esperada": (product["sale_price"] - product["avg_cost"]) * product["stock"],
    }
