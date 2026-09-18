"""Pantallas de arranque: creacion del administrador inicial y login."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable

from .. import models, security
from ..db import Database
from ..version import version_string


class PasswordEntry(ttk.Frame):
    """Entry de contrasena con boton para mostrar/ocultar."""

    def __init__(self, parent):
        super().__init__(parent)
        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.var, show="*", width=28)
        self.entry.grid(row=0, column=0, sticky="we")
        self._shown = False
        self.toggle = ttk.Button(self, text="Mostrar", width=8, command=self._toggle)
        self.toggle.grid(row=0, column=1, padx=(4, 0))
        self.columnconfigure(0, weight=1)

    def _toggle(self):
        self._shown = not self._shown
        self.entry.configure(show="" if self._shown else "*")
        self.toggle.configure(text="Ocultar" if self._shown else "Mostrar")

    def get(self) -> str:
        return self.var.get()


class FirstRunFrame(ttk.Frame):
    """Se muestra una unica vez: crear el primer usuario administrador."""

    def __init__(self, parent, *, db: Database, on_done: Callable[[], None]):
        super().__init__(parent, padding=24)
        self.db = db
        self.on_done = on_done

        ttk.Label(self, text="Configuracion inicial", font=("TkDefaultFont", 16, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 4), sticky="w"
        )
        ttk.Label(
            self,
            text="No existe una base de datos previa. Crea la cuenta de administrador.",
            wraplength=420,
        ).grid(row=1, column=0, columnspan=2, pady=(0, 16), sticky="w")

        self.username_var = tk.StringVar()
        self.full_name_var = tk.StringVar()

        ttk.Label(self, text="Usuario:").grid(row=2, column=0, sticky="e", pady=4)
        ttk.Entry(self, textvariable=self.username_var, width=30).grid(row=2, column=1, pady=4, sticky="w")

        ttk.Label(self, text="Nombre completo:").grid(row=3, column=0, sticky="e", pady=4)
        ttk.Entry(self, textvariable=self.full_name_var, width=30).grid(row=3, column=1, pady=4, sticky="w")

        ttk.Label(self, text="Contrasena:").grid(row=4, column=0, sticky="e", pady=4)
        self.password_entry = PasswordEntry(self)
        self.password_entry.grid(row=4, column=1, pady=4, sticky="w")

        ttk.Label(self, text="Confirmar contrasena:").grid(row=5, column=0, sticky="e", pady=4)
        self.confirm_entry = PasswordEntry(self)
        self.confirm_entry.grid(row=5, column=1, pady=4, sticky="w")

        ttk.Label(
            self,
            text="Minimo 8 caracteres, con mayuscula, minuscula, numero y caracter especial.",
            foreground="#5b6472",
            wraplength=420,
        ).grid(row=6, column=0, columnspan=2, pady=(2, 16), sticky="w")

        ttk.Button(self, text="Crear administrador", command=self._submit).grid(
            row=7, column=0, columnspan=2, pady=(0, 4)
        )

        self.bind_all("<Return>", lambda _e: self._submit())

    def _submit(self):
        username = self.username_var.get().strip()
        full_name = self.full_name_var.get().strip()
        password = self.password_entry.get()
        confirm = self.confirm_entry.get()

        if not username or not full_name:
            messagebox.showerror("Datos incompletos", "El usuario y el nombre completo son obligatorios.")
            return
        if password != confirm:
            messagebox.showerror("Contrasenas distintas", "La contrasena y su confirmacion no coinciden.")
            return

        try:
            models.create_user(
                self.db.conn, actor=None, username=username, full_name=full_name,
                password=password, role=models.ADMIN,
            )
            self.db.persist()
        except security.PasswordPolicyError as exc:
            messagebox.showerror("Contrasena invalida", str(exc))
            return
        except ValueError as exc:
            messagebox.showerror("No se pudo crear el usuario", str(exc))
            return

        messagebox.showinfo("Listo", f"Administrador '{username}' creado correctamente.")
        self.on_done()


class LoginFrame(ttk.Frame):
    def __init__(self, parent, *, db: Database, on_success: Callable[[models.Session], None]):
        super().__init__(parent, padding=24)
        self.db = db
        self.on_success = on_success

        wrapper = ttk.Frame(self)
        wrapper.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(wrapper, text=version_string(), font=("TkDefaultFont", 18, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 16)
        )

        self.username_var = tk.StringVar()
        ttk.Label(wrapper, text="Usuario:").grid(row=1, column=0, sticky="e", pady=6)
        username_entry = ttk.Entry(wrapper, textvariable=self.username_var, width=28)
        username_entry.grid(row=1, column=1, pady=6, sticky="w")
        username_entry.focus_set()

        ttk.Label(wrapper, text="Contrasena:").grid(row=2, column=0, sticky="e", pady=6)
        self.password_entry = PasswordEntry(wrapper)
        self.password_entry.grid(row=2, column=1, pady=6, sticky="w")

        self.error_var = tk.StringVar()
        ttk.Label(wrapper, textvariable=self.error_var, foreground="#c0392b").grid(
            row=3, column=0, columnspan=2, pady=(4, 8)
        )

        ttk.Button(wrapper, text="Entrar", command=self._submit).grid(row=4, column=0, columnspan=2)

        self.bind_all("<Return>", lambda _e: self._submit())

    def _submit(self):
        username = self.username_var.get().strip()
        password = self.password_entry.get()
        try:
            session = models.authenticate(self.db.conn, username=username, password=password)
        except models.AuthError as exc:
            self.db.persist()  # conserva el intento fallido en el log aunque falle el login
            self.error_var.set(str(exc))
            return
        self.db.persist()
        self.error_var.set("")
        self.on_success(session)
