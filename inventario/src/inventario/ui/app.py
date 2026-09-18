"""Orquestador de la aplicacion: abre la BD y encadena arranque -> login -> ventana principal."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from .. import models
from ..db import Database
from ..paths import db_path, key_path
from ..version import version_string
from .login_window import FirstRunFrame, LoginFrame
from .main_window import MainFrame


class AppController:
    def __init__(self):
        self.db = Database(db_path(), key_path())

        self.root = tk.Tk()
        self.root.title(version_string())
        self.root.geometry("1050x680")
        self.root.minsize(860, 560)

        self.container = tk.Frame(self.root)
        self.container.pack(fill="both", expand=True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        if self.db.is_new:
            self.show_first_run()
        else:
            self.show_login()

    def _clear(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def show_first_run(self):
        self._clear()
        FirstRunFrame(self.container, db=self.db, on_done=self.show_login).pack(fill="both", expand=True)

    def show_login(self):
        self._clear()
        LoginFrame(self.container, db=self.db, on_success=self.show_main).pack(fill="both", expand=True)

    def show_main(self, session: models.Session):
        self._clear()
        MainFrame(self.container, db=self.db, session=session, on_logout=self.show_login).pack(fill="both", expand=True)

    def _on_close(self):
        if messagebox.askokcancel("Salir", "¿Cerrar la aplicacion? Los datos se guardan cifrados al salir."):
            try:
                self.db.close()
            finally:
                self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    AppController().run()


if __name__ == "__main__":
    main()
