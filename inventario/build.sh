#!/usr/bin/env bash
# Genera un ejecutable de Inventario para el sistema operativo ACTUAL.
# PyInstaller no hace cross-compilacion: para un .exe de Windows, este
# script debe correrse en Windows (usar build.bat) o en una VM/CI Windows.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -d .venv ]; then
    "$PYTHON_BIN" -m venv .venv
fi
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

pyinstaller --noconfirm --onefile --windowed --name Inventario --paths src main.py

echo
echo "Ejecutable generado en dist/Inventario"
echo "La primera vez que se ejecute creara una carpeta 'data' junto al ejecutable"
echo "con la base de datos cifrada (inventario.db.enc) y la llave (secret.key)."
echo "IMPORTANTE: respalda ambos archivos juntos; sin secret.key la BD no se puede leer."
