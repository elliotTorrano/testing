"""Ubicacion de los archivos de datos de la aplicacion (BD cifrada, llave, imagenes).

Por defecto los datos viven en una carpeta `data/` junto al ejecutable
(o junto al proyecto cuando se corre desde codigo fuente). Se puede
sobreescribir con la variable de entorno INVENTARIO_DATA_DIR, util para
pruebas o para apuntar a una carpeta compartida en red.
"""

from __future__ import annotations

import os
import sys


def get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        # Empaquetado con PyInstaller: junto al .exe
        return os.path.dirname(sys.executable)
    # Ejecutando desde codigo fuente: raiz del proyecto (carpeta 'inventario')
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_data_dir() -> str:
    base = os.environ.get("INVENTARIO_DATA_DIR") or os.path.join(get_base_dir(), "data")
    os.makedirs(base, exist_ok=True)
    return base


def db_path() -> str:
    return os.path.join(get_data_dir(), "inventario.db.enc")


def key_path() -> str:
    return os.path.join(get_data_dir(), "secret.key")


def images_dir() -> str:
    d = os.path.join(get_data_dir(), "imagenes")
    os.makedirs(d, exist_ok=True)
    return d
