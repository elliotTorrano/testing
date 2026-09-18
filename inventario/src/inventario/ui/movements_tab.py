"""Pestana de movimientos: registrar compras, ventas y ajustes de inventario."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from .. import models
from ..db import Database

TIPOS_TODOS = ("Compra", "Venta", "Ajuste")
TIPOS_CAPTURISTA = ("Compra", "Venta")

HIST_COLUMNS = ("date", "product", "type", "quantity", "unit_cost", "unit_price", "total", "expected_profit", "user")
HIST_HEADINGS = {
    "date": "Fecha",
    "product": "Producto",
    "type": "Tipo",
    "quantity": "Cantidad",
    "unit_cost": "Costo unit.",
    "unit_price": "Precio unit.",
    "total": "Total",
    "expected_profit": "Utilidad esperada",
    "user": "Usuario",
}


class MovementsTab(ttk.Frame):
    def __init__(self, parent, *, db: Database, session: models.Session):
        super().__init__(parent, padding=12)
        self.db = db
        self.session = session
        self._products_by_label: dict[str, int] = {}

        form = ttk.LabelFrame(self, text="Registrar movimiento", padding=12)
        form.pack(fill="x", pady=(0, 12))

        ttk.Label(form, text="Producto:").grid(row=0, column=0, sticky="e", pady=4)
        self.product_var = tk.StringVar()
        self.product_combo = ttk.Combobox(form, textvariable=self.product_var, state="readonly", width=32)
        self.product_combo.grid(row=0, column=1, pady=4, sticky="w")

        ttk.Label(form, text="Tipo:").grid(row=0, column=2, sticky="e", pady=4, padx=(16, 0))
        tipos = TIPOS_TODOS if session.is_admin else TIPOS_CAPTURISTA
        self.type_var = tk.StringVar(value=tipos[0])
        type_combo = ttk.Combobox(form, textvariable=self.type_var, state="readonly", values=tipos, width=12)
        type_combo.grid(row=0, column=3, pady=4, sticky="w")
        type_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_fields())

        # Cantidad (comun a los tres tipos, con distinto significado en ajuste)
        self.quantity_label = ttk.Label(form, text="Cantidad:")
        self.quantity_label.grid(row=1, column=0, sticky="e", pady=4)
        self.quantity_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.quantity_var, width=15).grid(row=1, column=1, pady=4, sticky="w")

        self.price_label = ttk.Label(form, text="Costo de compra:")
        self.price_label.grid(row=1, column=2, sticky="e", pady=4, padx=(16, 0))
        self.price_var = tk.StringVar()
        self.price_entry = ttk.Entry(form, textvariable=self.price_var, width=15)
        self.price_entry.grid(row=1, column=3, pady=4, sticky="w")

        self.note_label = ttk.Label(form, text="Nota:")
        self.note_label.grid(row=2, column=0, sticky="e", pady=4)
        self.note_var = tk.StringVar()
        self.note_entry = ttk.Entry(form, textvariable=self.note_var, width=40)
        self.note_entry.grid(row=2, column=1, columnspan=3, pady=4, sticky="w")

        ttk.Button(form, text="Registrar", command=self._submit).grid(row=3, column=0, columnspan=4, pady=(8, 0))

        history = ttk.LabelFrame(self, text="Historial de movimientos", padding=12)
        history.pack(fill="both", expand=True)
        ttk.Button(history, text="Actualizar", command=self.refresh).pack(anchor="w", pady=(0, 6))

        self.tree = ttk.Treeview(history, columns=HIST_COLUMNS, show="headings", height=12)
        for col in HIST_COLUMNS:
            self.tree.heading(col, text=HIST_HEADINGS[col])
            self.tree.column(col, width=110, anchor="center" if col != "product" else "w")
        self.tree.pack(fill="both", expand=True)

        self._update_fields()
        self.refresh_products()
        self.refresh()

    def refresh_products(self):
        known_ids = set(self._products_by_label.values())
        self._products_by_label.clear()
        labels = []
        new_labels = []
        for p in models.list_products(self.db.conn, only_active=True):
            label = f"{p['sku']} - {p['name']}"
            self._products_by_label[label] = p["id"]
            labels.append(label)
            if p["id"] not in known_ids:
                new_labels.append(label)
        self.product_combo.configure(values=labels)

        if not labels:
            return
        if not self.product_var.get():
            # primer llenado del combo: selecciona el primero
            self.product_var.set(labels[0])
        elif len(new_labels) == 1:
            # exactamente un producto nuevo desde el ultimo refresco: lo
            # selecciona para que quede visible que se agrego (si ya habia
            # una seleccion previa, el texto del combo no cambiaba solo).
            self.product_var.set(new_labels[0])

    def refresh(self):
        self.refresh_products()
        self.tree.delete(*self.tree.get_children())
        rows = models.list_movements(self.db.conn)
        products = {p["id"]: p["name"] for p in models.list_products(self.db.conn, only_active=False)}
        users = {u["id"]: u["username"] for u in models.list_users(self.db.conn)}
        for m in rows[:300]:
            self.tree.insert(
                "", "end",
                values=(
                    m["date"], products.get(m["product_id"], "?"), m["type"],
                    f"{m['quantity']:g}",
                    f"{m['unit_cost']:.2f}" if m["unit_cost"] is not None else "",
                    f"{m['unit_price']:.2f}" if m["unit_price"] is not None else "",
                    f"{m['total']:.2f}" if m["total"] is not None else "",
                    f"{m['expected_profit']:.2f}" if m["expected_profit"] is not None else "",
                    users.get(m["user_id"], "?"),
                ),
            )

    def _update_fields(self):
        tipo = self.type_var.get()
        if tipo == "Compra":
            self.quantity_label.configure(text="Cantidad comprada:")
            self.price_label.configure(text="Costo de compra (unit.):")
            self.price_entry.grid()
            self.price_label.grid()
            self.note_label.grid_remove()
            self.note_entry.grid_remove()
        elif tipo == "Venta":
            self.quantity_label.configure(text="Cantidad vendida:")
            self.price_label.configure(text="Precio de venta (unit.):")
            self.price_entry.grid()
            self.price_label.grid()
            self.note_label.grid_remove()
            self.note_entry.grid_remove()
        else:  # Ajuste
            self.quantity_label.configure(text="Nueva existencia total:")
            self.price_label.grid_remove()
            self.price_entry.grid_remove()
            self.note_label.grid()
            self.note_entry.grid()

    def _submit(self):
        label = self.product_var.get()
        product_id = self._products_by_label.get(label)
        if product_id is None:
            messagebox.showinfo("Selecciona un producto", "Elige un producto de la lista.")
            return

        tipo = self.type_var.get()
        try:
            quantity = float(self.quantity_var.get())
        except ValueError:
            messagebox.showerror("Cantidad invalida", "La cantidad debe ser un numero.")
            return

        try:
            if tipo == "Compra":
                unit_cost = float(self.price_var.get())
                models.register_purchase(
                    self.db.conn, actor=self.session, product_id=product_id,
                    quantity=quantity, unit_cost=unit_cost,
                )
            elif tipo == "Venta":
                unit_price = float(self.price_var.get())
                models.register_sale(
                    self.db.conn, actor=self.session, product_id=product_id,
                    quantity=quantity, unit_price=unit_price,
                )
            else:
                models.register_adjustment(
                    self.db.conn, actor=self.session, product_id=product_id,
                    new_stock=quantity, note=self.note_var.get().strip(),
                )
            self.db.persist()
        except ValueError as exc:
            messagebox.showerror("Precio invalido", "Revisa que el costo/precio sea un numero.\n\n" + str(exc))
            return
        except models.InsufficientStockError as exc:
            messagebox.showerror("Stock insuficiente", str(exc))
            return

        self.quantity_var.set("")
        self.price_var.set("")
        self.note_var.set("")
        self.refresh()
        messagebox.showinfo("Listo", f"{tipo} registrada correctamente.")
