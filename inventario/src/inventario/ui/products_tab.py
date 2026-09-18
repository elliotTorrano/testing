"""Pestana de catalogo de productos: listado y alta/edicion (solo administrador)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from .. import models
from ..db import Database
from . import images as img_utils

COLUMNS = ("sku", "name", "sale_price", "avg_cost", "stock", "expected_profit", "active")
HEADINGS = {
    "sku": "SKU",
    "name": "Producto",
    "sale_price": "Precio venta",
    "avg_cost": "Costo promedio",
    "stock": "Existencia",
    "expected_profit": "Utilidad esperada",
    "active": "Estado",
}


class ProductsTab(ttk.Frame):
    def __init__(self, parent, *, db: Database, session: models.Session):
        super().__init__(parent, padding=12)
        self.db = db
        self.session = session

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Actualizar", command=self.refresh).pack(side="left")
        if self.session.is_admin:
            ttk.Button(toolbar, text="Nuevo producto", command=self._new_product).pack(side="left", padx=6)
            self.toggle_btn = ttk.Button(toolbar, text="Activar/Desactivar", command=self._toggle_active)
            self.toggle_btn.pack(side="left")
            ttk.Button(toolbar, text="Editar", command=self._edit_selected).pack(side="left", padx=6)

        self.tree = ttk.Treeview(self, columns=COLUMNS, show="headings", selectmode="browse")
        for col in COLUMNS:
            self.tree.heading(col, text=HEADINGS[col])
            self.tree.column(col, width=110, anchor="center" if col != "name" else "w")
        self.tree.column("name", width=200)
        self.tree.pack(fill="both", expand=True)

        self.refresh()

    def _selected_product_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for p in models.list_products(self.db.conn, only_active=False):
            expected_profit = (p["sale_price"] - p["avg_cost"]) * p["stock"]
            self.tree.insert(
                "", "end", iid=str(p["id"]),
                values=(
                    p["sku"], p["name"],
                    f"{p['sale_price']:.2f}", f"{p['avg_cost']:.2f}",
                    f"{p['stock']:g}", f"{expected_profit:.2f}",
                    "Activo" if p["active"] else "Inactivo",
                ),
            )

    def _new_product(self):
        ProductDialog(self, db=self.db, session=self.session, on_saved=self.refresh)

    def _edit_selected(self):
        product_id = self._selected_product_id()
        if product_id is None:
            messagebox.showinfo("Selecciona un producto", "Elige un producto de la lista para editarlo.")
            return
        ProductDialog(self, db=self.db, session=self.session, product_id=product_id, on_saved=self.refresh)

    def _toggle_active(self):
        product_id = self._selected_product_id()
        if product_id is None:
            messagebox.showinfo("Selecciona un producto", "Elige un producto de la lista.")
            return
        product = models.get_product(self.db.conn, product_id)
        models.set_product_active(self.db.conn, actor=self.session, product_id=product_id, active=not product["active"])
        self.db.persist()
        self.refresh()


class ProductDialog(tk.Toplevel):
    def __init__(self, parent, *, db: Database, session: models.Session, on_saved, product_id: int | None = None):
        super().__init__(parent)
        self.db = db
        self.session = session
        self.on_saved = on_saved
        self.product_id = product_id
        self.image_path = None

        self.title("Editar producto" if product_id else "Nuevo producto")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        self.sku_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.sale_price_var = tk.StringVar()

        row = 0
        ttk.Label(frame, text="SKU:").grid(row=row, column=0, sticky="e", pady=4)
        self.sku_entry = ttk.Entry(frame, textvariable=self.sku_var, width=26)
        self.sku_entry.grid(row=row, column=1, pady=4, sticky="w")
        row += 1

        ttk.Label(frame, text="Nombre:").grid(row=row, column=0, sticky="e", pady=4)
        ttk.Entry(frame, textvariable=self.name_var, width=26).grid(row=row, column=1, pady=4, sticky="w")
        row += 1

        ttk.Label(frame, text="Precio de venta:").grid(row=row, column=0, sticky="e", pady=4)
        ttk.Entry(frame, textvariable=self.sale_price_var, width=26).grid(row=row, column=1, pady=4, sticky="w")
        row += 1

        ttk.Label(frame, text="Imagen:").grid(row=row, column=0, sticky="ne", pady=4)
        image_frame = ttk.Frame(frame)
        image_frame.grid(row=row, column=1, pady=4, sticky="w")
        self.preview_label = ttk.Label(image_frame, text="(sin imagen)")
        self.preview_label.pack(anchor="w")
        ttk.Button(image_frame, text="Elegir imagen...", command=self._choose_image).pack(anchor="w", pady=(4, 0))
        row += 1

        if product_id is None:
            note = "El costo promedio y la existencia inician en 0; se actualizan al registrar compras."
        else:
            note = "El costo promedio y la existencia se modifican solo con movimientos, no desde aqui."
        ttk.Label(frame, text=note, foreground="#5b6472", wraplength=280).grid(
            row=row, column=0, columnspan=2, pady=(4, 12), sticky="w"
        )
        row += 1

        ttk.Button(frame, text="Guardar", command=self._save).grid(row=row, column=0, columnspan=2)

        if product_id is not None:
            self._load_existing(product_id)

    def _load_existing(self, product_id: int):
        product = models.get_product(self.db.conn, product_id)
        self.sku_var.set(product["sku"])
        self.sku_entry.configure(state="disabled")  # el SKU no se cambia una vez creado
        self.name_var.set(product["name"])
        self.sale_price_var.set(f"{product['sale_price']:g}")
        self.image_path = product["image_path"]
        self._update_preview()

    def _choose_image(self):
        path = filedialog.askopenfilename(
            title="Selecciona una imagen",
            filetypes=[("Imagenes", "*.png *.gif *.ppm *.pgm *.jpg *.jpeg *.bmp"), ("Todos los archivos", "*.*")],
        )
        if not path:
            return
        self.image_path = img_utils.import_image(path)
        self._update_preview()

    def _update_preview(self):
        photo = img_utils.load_preview(self.image_path)
        if photo is not None:
            self._preview_photo = photo  # evita que el garbage collector la libere
            self.preview_label.configure(image=photo, text="")
        elif self.image_path:
            self.preview_label.configure(image="", text="(imagen guardada, sin vista previa)")
        else:
            self.preview_label.configure(image="", text="(sin imagen)")

    def _save(self):
        name = self.name_var.get().strip()
        try:
            sale_price = float(self.sale_price_var.get())
        except ValueError:
            messagebox.showerror("Precio invalido", "El precio de venta debe ser un numero.")
            return

        try:
            if self.product_id is None:
                sku = self.sku_var.get().strip()
                models.create_product(
                    self.db.conn, actor=self.session, sku=sku, name=name,
                    sale_price=sale_price, image_path=self.image_path,
                )
            else:
                models.update_product(
                    self.db.conn, actor=self.session, product_id=self.product_id,
                    name=name, sale_price=sale_price, image_path=self.image_path,
                )
            self.db.persist()
        except (ValueError, models.DuplicateSKUError) as exc:
            messagebox.showerror("No se pudo guardar", str(exc))
            return

        self.on_saved()
        self.destroy()
