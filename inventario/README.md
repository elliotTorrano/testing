# Inventario (modulo provisional)

Aplicacion de escritorio (Tkinter) para llevar un inventario con costeo
por **promedio ponderado**, base de datos cifrada en reposo, login con
politica de contrasenas, roles de administrador/capturista y trazabilidad
de cambios y de inicios de sesion.

## Requisitos

- Python 3.10+ con Tkinter incluido (el instalador oficial de
  [python.org](https://www.python.org/downloads/) lo incluye por
  defecto; en Linux instalar el paquete `python3-tk`).
- Dependencias en `requirements.txt` (`cryptography`, `pyinstaller`).

## Ejecutar desde codigo fuente

**Windows** (usa el lanzador `py`, instalado junto con Python desde
python.org; el comando `python` a veces no queda registrado en el PATH):

```bat
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

**Linux/Mac**:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

En ambos casos, una vez activado el entorno virtual (`.venv`), los comandos
`python` y `pip` ya apuntan al Python del entorno virtual (no hace falta
`py` ni `python3` despues de activarlo).

La primera vez que se ejecuta no existe base de datos: la aplicacion pide
crear la cuenta de **administrador** inicial. A partir de ahi se entra
por la pantalla de login normal.

## Generar el ejecutable

- **Windows**: correr `build.bat` (debe ejecutarse en Windows; PyInstaller
  no hace cross-compilacion desde otro sistema operativo). Genera
  `dist\Inventario.exe`.
- **Linux/Mac**: correr `./build.sh`. Genera `dist/Inventario`.

El ejecutable es independiente (no requiere Python instalado en el
equipo destino). Al ejecutarlo por primera vez crea junto a si mismo una
carpeta `data/` con:

- `inventario.db.enc` — la base de datos, cifrada.
- `secret.key` — la llave de cifrado de esa base de datos.

**Respalda ambos archivos juntos.** Sin `secret.key` la base de datos no
se puede leer; es equivalente a la llave de una caja fuerte, no a la
contrasena de ningun usuario (ver "Modelo de seguridad" abajo).

## Roles

| Accion | Administrador | Capturista |
|---|---|---|
| Ver catalogo de productos | Si | Si |
| Alta/edicion/baja de productos | Si | No |
| Registrar compras y ventas | Si | Si |
| Registrar ajustes de inventario (conteo fisico) | Si | No |
| Gestionar usuarios (alta, restablecer contrasena, activar/desactivar) | Si | No |
| Ver trazabilidad (login y cambios) | Si | No |

## Costeo por promedio ponderado

- En cada **compra** se recalcula el costo promedio del producto:
  `nuevo_promedio = (stock_actual * promedio_actual + cantidad * costo_unitario) / (stock_actual + cantidad)`.
- En cada **venta** el costo de venta es el promedio vigente en ese
  momento (queda congelado en el movimiento; no se recalcula despues).
- Los **ajustes** (conteo fisico) solo corrigen la existencia, nunca el
  costo promedio, y exigen una nota que explique el motivo.

## Modelo de seguridad

Son dos mecanismos independientes, a proposito:

- **Login y roles**: controla quien puede usar la aplicacion y que puede
  hacer. Las contrasenas se guardan como hash PBKDF2-HMAC-SHA256 con sal
  aleatoria (nunca en texto plano), y deben tener minimo 8 caracteres con
  mayuscula, minuscula, numero y caracter especial.
- **Cifrado de la base de datos**: el archivo `inventario.db.enc` esta
  cifrado con Fernet (AES). La llave (`secret.key`) es propia de la
  instalacion, **no** se deriva de la contrasena de ningun usuario. Esto
  protege el archivo de la base de datos si se copia o se pierde por
  separado del equipo (por ejemplo, si alguien sustrae solo el archivo
  `.db`), pero no sustituye a otras medidas (control de acceso al equipo,
  respaldo del `secret.key` en un lugar seguro, etc.). Es un diseno
  adecuado para un modulo provisional de una sola instalacion; no es un
  esquema multiusuario de llaves por persona.

## Trazabilidad

- `login_log`: cada intento de inicio de sesion (exitoso o fallido), con
  usuario, fecha/hora y equipo.
- `audit_log`: cada alta, edicion o baja relevante (productos, usuarios,
  movimientos de inventario), con el valor anterior y el nuevo.

Ambas se consultan desde la pestana "Trazabilidad" (solo administrador).

## Estructura del proyecto

```
inventario/
├── main.py                  # punto de entrada
├── requirements.txt
├── build.bat / build.sh     # empaquetado a ejecutable
├── src/inventario/
│   ├── security.py          # hashing de contrasenas y cifrado de la BD
│   ├── db.py                 # apertura/cierre de la BD cifrada, esquema
│   ├── models.py             # usuarios, productos, movimientos, costeo
│   ├── audit.py               # registro de login y de cambios
│   ├── paths.py               # ubicacion de los archivos de datos
│   ├── version.py
│   └── ui/                    # pantallas Tkinter
└── tests/
    ├── test_models.py         # logica de negocio (costeo, auditoria, etc.)
    └── test_ui_headless.py    # flujo de la interfaz real bajo Xvfb
```

## Pruebas

```bash
python tests/test_models.py
# Prueba de interfaz (requiere Tkinter y, en Linux sin entorno grafico, Xvfb):
xvfb-run -a python tests/test_ui_headless.py
```

## Limitaciones conocidas (modulo provisional)

- La vista previa de imagenes de producto solo funciona para PNG/GIF/PPM
  (limitacion de Tkinter sin Pillow); otros formatos se guardan pero sin
  miniatura.
- Un solo usuario a la vez por instalacion (no es multiusuario en red
  simultanea: la BD se descifra a un archivo temporal local mientras la
  aplicacion esta abierta).
- No incluye reportes impresos ni exportacion a Excel/PDF todavia.
