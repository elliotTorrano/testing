# Historial de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Versionado semantico: MAYOR.MENOR.PARCHE.

## [1.0.0] - 2026-09-18

### Agregado
- Catalogo de productos con imagen, SKU, nombre, precio de venta, costo
  promedio, existencia y utilidad esperada.
- Movimientos de compra, venta y ajuste de inventario con costeo por
  **promedio ponderado** (el costo promedio se recalcula en cada compra;
  las ventas usan el costo congelado al momento de vender).
- Base de datos SQLite cifrada en reposo (Fernet/AES) con llave propia
  de la instalacion.
- Inicio de sesion con politica de contrasena obligatoria (minimo 8
  caracteres, mayuscula, minuscula, numero y caracter especial).
- Roles de **administrador** y **capturista** con permisos diferenciados.
- Trazabilidad completa: bitacora de inicios de sesion (exitosos y
  fallidos) y bitacora de cambios (alta/edicion/baja) con valores
  anteriores y nuevos.
- Empaquetado a ejecutable independiente con PyInstaller.
