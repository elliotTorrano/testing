"""Pestana de administracion de usuarios (solo administrador)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from .. import models, security
from ..db import Database
from .login_window import PasswordEntry

COLUMNS = ("username", "full_name", "role", "active", "created_at")
HEADINGS = {
    "username": "Usuario",
    "full_name": "Nombre completo",
    "role": "Rol",
    "active": "Estado",
    "created_at": "Creado",
}


class UsersTab(ttk.Frame):
    def __init__(self, parent, *, db: Database, session: models.Session):
        super().__init__(parent, padding=12)
        self.db = db
        self.session = session

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Actualizar", command=self.refresh).pack(side="left")
        ttk.Button(toolbar, text="Nuevo usuario", command=self._new_user).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Restablecer contrasena", command=self._reset_password).pack(side="left")
        ttk.Button(toolbar, text="Activar/Desactivar", command=self._toggle_active).pack(side="left", padx=6)

        self.tree = ttk.Treeview(self, columns=COLUMNS, show="headings")
        for col in COLUMNS:
            self.tree.heading(col, text=HEADINGS[col])
            self.tree.column(col, width=140, anchor="center" if col != "full_name" else "w")
        self.tree.pack(fill="both", expand=True)

        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for u in models.list_users(self.db.conn):
            iid = str(u["id"])
            self.tree.insert(
                "", "end", iid=iid,
                values=(u["username"], u["full_name"], u["role"], "Activo" if u["active"] else "Inactivo", u["created_at"]),
            )

    def _selected_user_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _new_user(self):
        NewUserDialog(self, db=self.db, session=self.session, on_saved=self.refresh)

    def _toggle_active(self):
        user_id = self._selected_user_id()
        if user_id is None:
            messagebox.showinfo("Selecciona un usuario", "Elige un usuario de la lista.")
            return
        if user_id == self.session.id:
            messagebox.showerror("Accion no permitida", "No puedes desactivar tu propia cuenta.")
            return
        row = next(u for u in models.list_users(self.db.conn) if u["id"] == user_id)
        models.set_user_active(self.db.conn, actor=self.session, user_id=user_id, active=not row["active"])
        self.db.persist()
        self.refresh()

    def _reset_password(self):
        user_id = self._selected_user_id()
        if user_id is None:
            messagebox.showinfo("Selecciona un usuario", "Elige un usuario de la lista.")
            return
        ResetPasswordDialog(self, db=self.db, session=self.session, user_id=user_id)


class NewUserDialog(tk.Toplevel):
    def __init__(self, parent, *, db: Database, session: models.Session, on_saved):
        super().__init__(parent)
        self.db = db
        self.session = session
        self.on_saved = on_saved
        self.title("Nuevo usuario")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        self.username_var = tk.StringVar()
        self.full_name_var = tk.StringVar()
        self.role_var = tk.StringVar(value=models.CAPTURISTA)

        ttk.Label(frame, text="Usuario:").grid(row=0, column=0, sticky="e", pady=4)
        ttk.Entry(frame, textvariable=self.username_var, width=26).grid(row=0, column=1, pady=4, sticky="w")

        ttk.Label(frame, text="Nombre completo:").grid(row=1, column=0, sticky="e", pady=4)
        ttk.Entry(frame, textvariable=self.full_name_var, width=26).grid(row=1, column=1, pady=4, sticky="w")

        ttk.Label(frame, text="Rol:").grid(row=2, column=0, sticky="e", pady=4)
        ttk.Combobox(
            frame, textvariable=self.role_var, state="readonly",
            values=[models.ADMIN, models.CAPTURISTA], width=23,
        ).grid(row=2, column=1, pady=4, sticky="w")

        ttk.Label(frame, text="Contrasena:").grid(row=3, column=0, sticky="e", pady=4)
        self.password_entry = PasswordEntry(frame)
        self.password_entry.grid(row=3, column=1, pady=4, sticky="w")

        ttk.Label(
            frame, text="Minimo 8 caracteres, con mayuscula, minuscula, numero y caracter especial.",
            foreground="#5b6472", wraplength=260,
        ).grid(row=4, column=0, columnspan=2, pady=(2, 12), sticky="w")

        ttk.Button(frame, text="Crear", command=self._submit).grid(row=5, column=0, columnspan=2)

    def _submit(self):
        try:
            models.create_user(
                self.db.conn, actor=self.session,
                username=self.username_var.get().strip(),
                full_name=self.full_name_var.get().strip(),
                password=self.password_entry.get(),
                role=self.role_var.get(),
            )
            self.db.persist()
        except (ValueError, security.PasswordPolicyError) as exc:
            messagebox.showerror("No se pudo crear el usuario", str(exc))
            return
        self.on_saved()
        self.destroy()


class ResetPasswordDialog(tk.Toplevel):
    def __init__(self, parent, *, db: Database, session: models.Session, user_id: int):
        super().__init__(parent)
        self.db = db
        self.session = session
        self.user_id = user_id
        self.title("Restablecer contrasena")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Nueva contrasena:").grid(row=0, column=0, sticky="e", pady=4)
        self.password_entry = PasswordEntry(frame)
        self.password_entry.grid(row=0, column=1, pady=4, sticky="w")

        ttk.Label(
            frame, text="Minimo 8 caracteres, con mayuscula, minuscula, numero y caracter especial.",
            foreground="#5b6472", wraplength=260,
        ).grid(row=1, column=0, columnspan=2, pady=(2, 12), sticky="w")

        ttk.Button(frame, text="Guardar", command=self._submit).grid(row=2, column=0, columnspan=2)

    def _submit(self):
        try:
            models.change_password(
                self.db.conn, actor=self.session, user_id=self.user_id,
                new_password=self.password_entry.get(),
            )
            self.db.persist()
        except security.PasswordPolicyError as exc:
            messagebox.showerror("Contrasena invalida", str(exc))
            return
        messagebox.showinfo("Listo", "Contrasena actualizada.")
        self.destroy()
