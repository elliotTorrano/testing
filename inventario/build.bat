@echo off
REM Genera Inventario.exe (Windows). Debe ejecutarse en Windows con Python
REM instalado desde python.org (incluye tkinter por defecto).
setlocal
cd /d "%~dp0"

if not exist .venv (
    py -m venv .venv
)
call .venv\Scripts\activate.bat

python -m pip install --upgrade pip
pip install -r requirements.txt

pyinstaller --noconfirm --onefile --windowed --name Inventario --paths src main.py

echo.
echo Ejecutable generado en dist\Inventario.exe
echo La primera vez que se ejecute creara una carpeta 'data' junto al .exe
echo con la base de datos cifrada (inventario.db.enc) y la llave (secret.key).
echo IMPORTANTE: respalda ambos archivos juntos; sin secret.key la BD no se puede leer.
pause
