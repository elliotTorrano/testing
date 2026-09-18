"""Seguridad: contrasenas de usuario y cifrado de la base de datos en reposo.

Dos mecanismos independientes:
  - Hash de contrasenas de usuario (PBKDF2-HMAC-SHA256 + salt) para el login.
  - Cifrado simetrico (Fernet/AES) del archivo de base de datos, con una
    llave propia de la instalacion (secret.key). La llave de cifrado de la
    BD NO se deriva de la contrasena de ningun usuario: el login controla
    quien puede usar la aplicacion y que puede hacer, el cifrado de archivo
    protege el .db si se copia o se pierde por separado del equipo.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets

from cryptography.fernet import Fernet, InvalidToken

PBKDF2_ITERATIONS = 200_000
SALT_BYTES = 16

PASSWORD_MIN_LENGTH = 8
_PASSWORD_RULES = (
    (re.compile(r"[a-z]"), "una letra minuscula"),
    (re.compile(r"[A-Z]"), "una letra mayuscula"),
    (re.compile(r"[0-9]"), "un numero"),
    (re.compile(r"[^A-Za-z0-9]"), "un caracter especial"),
)


class PasswordPolicyError(ValueError):
    """La contrasena no cumple la politica minima."""


def validate_password_policy(password: str) -> None:
    """Lanza PasswordPolicyError con el detalle de lo que falta, o no hace nada si es valida."""
    faltantes = []
    if len(password) < PASSWORD_MIN_LENGTH:
        faltantes.append(f"al menos {PASSWORD_MIN_LENGTH} caracteres")
    for pattern, descripcion in _PASSWORD_RULES:
        if not pattern.search(password):
            faltantes.append(descripcion)
    if faltantes:
        raise PasswordPolicyError(
            "La contrasena debe incluir: " + ", ".join(faltantes) + "."
        )


def hash_password(password: str) -> tuple[str, str]:
    """Devuelve (hash_hex, salt_hex) para guardar en la BD."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return digest.hex(), salt.hex()


def verify_password(password: str, hash_hex: str, salt_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return secrets.compare_digest(digest.hex(), hash_hex)


# --- Cifrado de la base de datos en reposo -------------------------------


def load_or_create_key(key_path: str) -> bytes:
    """Carga la llave de cifrado de la instalacion, generandola si no existe."""
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            return f.read()
    key = Fernet.generate_key()
    os.makedirs(os.path.dirname(key_path) or ".", exist_ok=True)
    with open(key_path, "wb") as f:
        f.write(key)
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass  # no soportado en algunos sistemas de archivos (p.ej. FAT en Windows)
    return key


def encrypt_bytes(data: bytes, key: bytes) -> bytes:
    return Fernet(key).encrypt(data)


def decrypt_bytes(token: bytes, key: bytes) -> bytes:
    try:
        return Fernet(key).decrypt(token)
    except InvalidToken as exc:
        raise ValueError(
            "No se pudo descifrar la base de datos: la llave (secret.key) no "
            "corresponde a este archivo, o el archivo esta danado."
        ) from exc
