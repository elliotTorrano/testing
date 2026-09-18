"""Version del programa (semver: MAYOR.MENOR.PARCHE)."""

__version__ = "1.0.0"

APP_NAME = "Inventario"


def version_string() -> str:
    return f"{APP_NAME} v{__version__}"
