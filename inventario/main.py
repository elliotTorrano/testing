"""Punto de entrada para ejecutar desde codigo fuente o empaquetar con PyInstaller."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from inventario.ui.app import main  # noqa: E402

if __name__ == "__main__":
    main()
