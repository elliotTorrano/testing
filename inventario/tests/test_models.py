"""Pruebas de logica de negocio: usuarios, costeo promedio ponderado y auditoria.

Ejecutar con: python3 -m pytest tests/  (o directamente con python3 tests/test_models.py)
"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from inventario.db import Database
from inventario import models


def make_db():
    workdir = tempfile.mkdtemp()
    db = Database(os.path.join(workdir, "inventario.db.enc"), os.path.join(workdir, "secret.key"))
    return db, workdir


def test_create_user_and_authenticate():
    db, workdir = make_db()
    try:
        models.create_user(
            db.conn, actor=None, username="admin", full_name="Admin",
            password="Abcdefg1!", role=models.ADMIN,
        )
        session = models.authenticate(db.conn, username="admin", password="Abcdefg1!")
        assert session.role == models.ADMIN

        try:
            models.authenticate(db.conn, username="admin", password="incorrecta")
            assert False, "debia fallar con contrasena incorrecta"
        except models.AuthError:
            pass

        logins = db.conn.execute("SELECT success FROM login_log ORDER BY id").fetchall()
        assert [r["success"] for r in logins] == [1, 0]
        print("test_create_user_and_authenticate OK")
    finally:
        db.close()
        shutil.rmtree(workdir)


def test_weak_password_rejected():
    db, workdir = make_db()
    try:
        try:
            models.create_user(
                db.conn, actor=None, username="x", full_name="X",
                password="debil", role=models.CAPTURISTA,
            )
            assert False, "debia rechazar contrasena debil"
        except Exception:
            pass
        print("test_weak_password_rejected OK")
    finally:
        db.close()
        shutil.rmtree(workdir)


def test_weighted_average_cost():
    db, workdir = make_db()
    try:
        admin_id = models.create_user(
            db.conn, actor=None, username="admin", full_name="Admin",
            password="Abcdefg1!", role=models.ADMIN,
        )
        actor = models.Session(id=admin_id, username="admin", full_name="Admin", role=models.ADMIN)

        product_id = models.create_product(
            db.conn, actor=actor, sku="SKU-1", name="Producto de prueba", sale_price=150.0,
        )

        # Compra 1: 10 unidades a 100 -> promedio 100
        models.register_purchase(db.conn, actor=actor, product_id=product_id, quantity=10, unit_cost=100.0)
        p = models.get_product(db.conn, product_id)
        assert p["stock"] == 10
        assert abs(p["avg_cost"] - 100.0) < 1e-9

        # Compra 2: 10 unidades a 120 -> promedio (10*100 + 10*120)/20 = 110
        models.register_purchase(db.conn, actor=actor, product_id=product_id, quantity=10, unit_cost=120.0)
        p = models.get_product(db.conn, product_id)
        assert p["stock"] == 20
        assert abs(p["avg_cost"] - 110.0) < 1e-9

        # Venta de 5 unidades a 150: costo de venta congelado en 110, no cambia el promedio
        mov_id = models.register_sale(db.conn, actor=actor, product_id=product_id, quantity=5, unit_price=150.0)
        p = models.get_product(db.conn, product_id)
        assert p["stock"] == 15
        assert abs(p["avg_cost"] - 110.0) < 1e-9

        mov = db.conn.execute("SELECT * FROM movements WHERE id = ?", (mov_id,)).fetchone()
        assert abs(mov["unit_cost"] - 110.0) < 1e-9
        assert abs(mov["total"] - 750.0) < 1e-9
        assert abs(mov["expected_profit"] - (150.0 - 110.0) * 5) < 1e-9

        # Venta que excede el stock disponible debe rechazarse
        try:
            models.register_sale(db.conn, actor=actor, product_id=product_id, quantity=1000, unit_price=150.0)
            assert False, "debia rechazar venta con stock insuficiente"
        except models.InsufficientStockError:
            pass

        # Ajuste de inventario (conteo fisico): baja de 15 a 12, no toca el promedio
        models.register_adjustment(db.conn, actor=actor, product_id=product_id, new_stock=12, note="Conteo fisico mensual")
        p = models.get_product(db.conn, product_id)
        assert p["stock"] == 12
        assert abs(p["avg_cost"] - 110.0) < 1e-9

        summary = models.product_summary(db.conn, product_id)
        assert abs(summary["venta_total"] - 750.0) < 1e-9
        assert abs(summary["costo_ventas"] - 550.0) < 1e-9
        assert abs(summary["utilidad_real"] - 200.0) < 1e-9

        audit_rows = db.conn.execute(
            "SELECT table_name, action FROM audit_log ORDER BY id"
        ).fetchall()
        assert len(audit_rows) >= 6, "debe haber quedado rastro de auditoria de cada operacion"

        print("test_weighted_average_cost OK")
    finally:
        db.close()
        shutil.rmtree(workdir)


def test_duplicate_sku_rejected():
    db, workdir = make_db()
    try:
        admin_id = models.create_user(
            db.conn, actor=None, username="admin", full_name="Admin",
            password="Abcdefg1!", role=models.ADMIN,
        )
        actor = models.Session(id=admin_id, username="admin", full_name="Admin", role=models.ADMIN)
        models.create_product(db.conn, actor=actor, sku="DUP-1", name="Uno", sale_price=10.0)
        try:
            models.create_product(db.conn, actor=actor, sku="DUP-1", name="Otro", sale_price=20.0)
            assert False, "debia rechazar SKU duplicado"
        except models.DuplicateSKUError:
            pass
        print("test_duplicate_sku_rejected OK")
    finally:
        db.close()
        shutil.rmtree(workdir)


if __name__ == "__main__":
    test_create_user_and_authenticate()
    test_weak_password_rejected()
    test_weighted_average_cost()
    test_duplicate_sku_rejected()
    print("\nTodas las pruebas pasaron.")
