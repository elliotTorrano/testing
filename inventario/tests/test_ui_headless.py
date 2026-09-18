"""Prueba funcional de la interfaz bajo un display virtual (Xvfb).

No es una prueba visual (no hay forma de "ver" la ventana en este entorno),
pero SI ejercita el codigo real de los widgets: crea el administrador
inicial a traves de FirstRunFrame, inicia sesion a traves de LoginFrame,
navega la ventana principal y registra una compra/venta reales a traves
del formulario de movimientos, verificando que los datos queden en la BD.

Ejecutar bajo Xvfb, p.ej.:
    xvfb-run -a python3.12 tests/test_ui_headless.py
"""

import os
import sys
import shutil
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

workdir = tempfile.mkdtemp()
os.environ["INVENTARIO_DATA_DIR"] = workdir

from tkinter import messagebox  # noqa: E402

# Los dialogos modales (messagebox.showinfo/showerror/askokcancel) bloquean
# esperando un clic real; para automatizar la prueba se reemplazan por
# no-ops que no interrumpen el flujo (equivalen a que el usuario da "OK").
messagebox.showinfo = lambda *a, **k: None
messagebox.showerror = lambda *a, **k: None
messagebox.askokcancel = lambda *a, **k: True

from inventario.ui.app import AppController  # noqa: E402
from inventario import models  # noqa: E402


def run():
    app = AppController()
    root = app.root

    # --- Pantalla de primer arranque: crear administrador ---
    first_run = app.container.winfo_children()[0]
    first_run.username_var.set("admin")
    first_run.full_name_var.set("Administrador General")
    first_run.password_entry.var.set("Abcdefg1!")
    first_run.confirm_entry.var.set("Abcdefg1!")
    first_run._submit()
    root.update()

    login = app.container.winfo_children()[0]
    assert login.__class__.__name__ == "LoginFrame", "debia mostrar la pantalla de login tras crear el admin"

    # --- Login con contrasena incorrecta: debe mostrar error y quedar en login ---
    login.username_var.set("admin")
    login.password_entry.var.set("incorrecta")
    login._submit()
    root.update()
    assert login.error_var.get(), "debia mostrar un mensaje de error con credenciales invalidas"

    # --- Login correcto ---
    login.password_entry.var.set("Abcdefg1!")
    login._submit()
    root.update()

    main_frame = app.container.winfo_children()[0]
    assert main_frame.__class__.__name__ == "MainFrame", "debia mostrar la ventana principal tras login"
    assert main_frame.session.role == models.ADMIN
    print("Login y navegacion inicial: OK")

    def create_product(sku, name, sale_price):
        products_tab._new_product()
        root.update()
        from inventario.ui.products_tab import ProductDialog
        dialogs = [w for w in products_tab.winfo_children() if isinstance(w, ProductDialog)]
        assert dialogs, "debia abrirse el dialogo de nuevo producto"
        dlg = dialogs[0]
        dlg.sku_var.set(sku)
        dlg.name_var.set(name)
        dlg.sale_price_var.set(str(sale_price))
        dlg._save()
        root.update()

    # --- Crear un primer producto desde la pestana Productos ---
    notebook = [w for w in main_frame.winfo_children() if w.winfo_class() == "TNotebook"][0]
    products_tab = notebook.winfo_children()[0]
    create_product("SKU-A", "Producto A", 10.0)
    products = models.list_products(app.db.conn)
    assert any(p["sku"] == "SKU-A" for p in products), "el producto no quedo guardado en la BD"
    print("Alta de producto desde la UI: OK")

    # --- Cambiar a la pestana Movimientos debe refrescarla sola (regresion:
    #     un producto nuevo no aparecia en el combo hasta pulsar "Actualizar"
    #     ahi manualmente), y con un solo producto debe quedar seleccionado ---
    movements_tab = notebook.winfo_children()[1]
    notebook.select(movements_tab)
    root.update()
    assert movements_tab.product_var.get().startswith("SKU-A")

    # --- Regresion reportada por el usuario: con un producto YA seleccionado,
    #     crear un segundo producto y refrescar (manualmente o cambiando de
    #     pestana) debe hacer visible el nuevo producto seleccionandolo,
    #     no dejarlo "escondido" en la lista sin cambiar el texto del combo ---
    notebook.select(products_tab)
    root.update()
    create_product("SKU-TEST", "Producto de prueba UI", 199.90)
    notebook.select(movements_tab)
    root.update()
    assert movements_tab.product_var.get().startswith("SKU-TEST"), (
        "el producto recien creado debia quedar seleccionado y visible en el combo, "
        f"pero sigue mostrando: {movements_tab.product_var.get()!r}"
    )
    label = [l for l in movements_tab._products_by_label if l.startswith("SKU-TEST")][0]
    movements_tab.product_var.set(label)

    movements_tab.type_var.set("Compra")
    movements_tab._update_fields()
    movements_tab.quantity_var.set("10")
    movements_tab.price_var.set("50")
    movements_tab._submit()
    root.update()

    movements_tab.type_var.set("Venta")
    movements_tab._update_fields()
    root.update()
    # El precio de venta debe proponerse solo, tomado del catalogo (199.90),
    # pero seguir siendo editable para esa venta puntual.
    assert abs(float(movements_tab.price_var.get()) - 199.90) < 1e-9, (
        f"el precio de venta debia proponerse en 199.90, mostro: {movements_tab.price_var.get()!r}"
    )
    movements_tab.quantity_var.set("4")
    movements_tab.price_var.set("80")  # el usuario lo cambia para esta venta puntual
    movements_tab._submit()
    root.update()

    # Tras registrar, el campo vuelve a proponer el precio de catalogo
    # (no queda vacio ni con el valor puntual de la venta anterior).
    assert abs(float(movements_tab.price_var.get()) - 199.90) < 1e-9
    print("Precio de venta autocompletado desde el catalogo: OK")

    product_id = movements_tab._products_by_label[label]
    summary = models.product_summary(app.db.conn, product_id)
    assert abs(summary["stock"] - 6) < 1e-9, summary
    assert abs(summary["costo_promedio"] - 50) < 1e-9, summary
    assert abs(summary["venta_total"] - 320) < 1e-9, summary
    assert abs(summary["utilidad_real"] - 120) < 1e-9, summary
    print("Registro de compra/venta desde la UI y costeo promedio: OK")

    # --- La pestana de trazabilidad debe reflejar los cambios ---
    audit_tab = notebook.winfo_children()[3]
    audit_tab.refresh()
    root.update()
    assert len(audit_tab.audit_tree.get_children()) > 0
    assert len(audit_tab.login_tree.get_children()) >= 2  # el intento fallido y el exitoso
    print("Pestana de trazabilidad: OK")

    # --- Cerrar sesion y volver a login ---
    main_frame.on_logout()
    root.update()
    back_to_login = app.container.winfo_children()[0]
    assert back_to_login.__class__.__name__ == "LoginFrame"
    print("Cerrar sesion: OK")

    app.db.close()
    root.destroy()


if __name__ == "__main__":
    try:
        run()
        print("\nTodas las pruebas de UI (headless) pasaron.")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
