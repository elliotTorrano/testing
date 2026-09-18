"""Ventana principal: barra superior con la sesion activa y pestanas por rol."""

from __future__ import annotations

from tkinter import ttk, messagebox
from typing import Callable

from .. import models
from ..db import Database
from ..version import version_string
from .audit_tab import AuditTab
from .movements_tab import MovementsTab
from .products_tab import ProductsTab
from .users_tab import UsersTab


class MainFrame(ttk.Frame):
    def __init__(self, parent, *, db: Database, session: models.Session, on_logout: Callable[[], None]):
        super().__init__(parent)
        self.db = db
        self.session = session
        self.on_logout = on_logout

        topbar = ttk.Frame(self, padding=(12, 8))
        topbar.pack(fill="x")
        ttk.Label(
            topbar,
            text=f"{session.full_name}  ·  {session.role}",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side="left")
        ttk.Button(topbar, text="Acerca de", command=self._show_about).pack(side="right")
        ttk.Button(topbar, text="Cerrar sesion", command=self._logout).pack(side="right", padx=(0, 8))
        ttk.Separator(self).pack(fill="x")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        notebook.add(ProductsTab(notebook, db=db, session=session), text="Productos")
        notebook.add(MovementsTab(notebook, db=db, session=session), text="Movimientos")
        if session.is_admin:
            notebook.add(UsersTab(notebook, db=db, session=session), text="Usuarios")
            notebook.add(AuditTab(notebook, db=db), text="Trazabilidad")

    def _show_about(self):
        messagebox.showinfo(
            "Acerca de",
            f"{version_string()}\n\n"
            "Modulo de inventario provisional.\n"
            "Costeo por promedio ponderado, base de datos cifrada en reposo,\n"
            "control de acceso por roles y trazabilidad de cambios.",
        )

    def _logout(self):
        if messagebox.askokcancel("Cerrar sesion", "¿Cerrar la sesion actual?"):
            self.on_logout()
