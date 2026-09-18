"""Utilidades de imagenes de producto: copiar a la carpeta de datos y previsualizar.

Tkinter (sin Pillow) solo puede mostrar PNG/GIF/PPM de forma nativa. Se
acepta cualquier archivo como imagen del producto (se guarda la ruta), pero
la vista previa solo se muestra para esos formatos; para el resto se
indica que no hay previsualizacion disponible.
"""

from __future__ import annotations

import os
import shutil
import tkinter as tk
import uuid
from typing import Optional

from ..paths import images_dir

_PREVIEWABLE_EXTENSIONS = {".png", ".gif", ".ppm", ".pgm"}


def import_image(source_path: str) -> str:
    """Copia la imagen elegida a la carpeta de datos y devuelve la ruta guardada."""
    ext = os.path.splitext(source_path)[1].lower()
    dest_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(images_dir(), dest_name)
    shutil.copyfile(source_path, dest_path)
    return dest_path


def load_preview(path: Optional[str], max_size: int = 160) -> Optional[tk.PhotoImage]:
    """Devuelve un PhotoImage reducido, o None si no hay imagen o el formato no es previsualizable."""
    if not path or not os.path.exists(path):
        return None
    ext = os.path.splitext(path)[1].lower()
    if ext not in _PREVIEWABLE_EXTENSIONS:
        return None
    try:
        image = tk.PhotoImage(file=path)
    except tk.TclError:
        return None
    factor = max(1, image.width() // max_size, image.height() // max_size)
    if factor > 1:
        image = image.subsample(factor, factor)
    return image


def is_previewable(path: Optional[str]) -> bool:
    if not path:
        return False
    return os.path.splitext(path)[1].lower() in _PREVIEWABLE_EXTENSIONS
