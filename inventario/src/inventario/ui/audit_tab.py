"""Pestana de trazabilidad: historial de inicios de sesion y de cambios (solo administrador)."""

from __future__ import annotations

from tkinter import ttk

from ..db import Database

LOGIN_COLUMNS = ("timestamp", "username", "success", "hostname")
LOGIN_HEADINGS = {"timestamp": "Fecha/hora", "username": "Usuario", "success": "Resultado", "hostname": "Equipo"}

AUDIT_COLUMNS = ("timestamp", "username", "table_name", "record_id", "action", "old_value", "new_value")
AUDIT_HEADINGS = {
    "timestamp": "Fecha/hora",
    "username": "Usuario",
    "table_name": "Tabla",
    "record_id": "ID registro",
    "action": "Accion",
    "old_value": "Valor anterior",
    "new_value": "Valor nuevo",
}


class AuditTab(ttk.Frame):
    def __init__(self, parent, *, db: Database):
        super().__init__(parent, padding=12)
        self.db = db

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self.login_tree = self._build_tree(notebook, LOGIN_COLUMNS, LOGIN_HEADINGS, "Inicios de sesion")
        self.audit_tree = self._build_tree(notebook, AUDIT_COLUMNS, AUDIT_HEADINGS, "Cambios de datos")

        ttk.Button(self, text="Actualizar", command=self.refresh).pack(anchor="w", pady=(8, 0))
        self.refresh()

    def _build_tree(self, notebook, columns, headings, tab_title):
        container = ttk.Frame(notebook, padding=8)
        notebook.add(container, text=tab_title)
        tree = ttk.Treeview(container, columns=columns, show="headings")
        for col in columns:
            tree.heading(col, text=headings[col])
            width = 220 if col in ("old_value", "new_value") else 130
            tree.column(col, width=width, anchor="w")
        tree.pack(fill="both", expand=True)
        return tree

    def refresh(self):
        self.login_tree.delete(*self.login_tree.get_children())
        for r in self.db.conn.execute("SELECT * FROM login_log ORDER BY id DESC LIMIT 500"):
            self.login_tree.insert(
                "", "end",
                values=(r["timestamp"], r["username"], "Exitoso" if r["success"] else "Fallido", r["hostname"] or ""),
            )

        self.audit_tree.delete(*self.audit_tree.get_children())
        for r in self.db.conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 500"):
            self.audit_tree.insert(
                "", "end",
                values=(
                    r["timestamp"], r["username"], r["table_name"], r["record_id"] or "",
                    r["action"], r["old_value"] or "", r["new_value"] or "",
                ),
            )
