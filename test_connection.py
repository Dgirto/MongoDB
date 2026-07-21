"""Prueba de conexión estándar del conector mongodb.

Firma estándar Ruvic: def test_connection() -> tuple[bool, str]
- Lee la configuración EXCLUSIVAMENTE de las env vars RUVIC_MONGODB_*.
- Nunca lanza excepciones; retorna (ok, mensaje).

Ejecutable también como script para pruebas locales:
    python test_connection.py
"""

from __future__ import annotations


def test_connection() -> tuple[bool, str]:
    """Conecta a MongoDB y ejecuta el comando ping usando las env vars RUVIC_MONGODB_*."""
    try:
        from ruvic_mongodb_connector import (
            MongodbAuthError,
            MongodbClient,
            MongodbDataError,
            MongodbNetworkError,
        )
    except ImportError:
        return (
            False,
            "La librería ruvic-mongodb-connector no está instalada. "
            "Instala con: pip install git+https://github.com/Dgirto/"
            "MongoDB.git#subdirectory=lib",
        )

    try:
        client = MongodbClient()  # valida que existan las env vars
    except ValueError as exc:
        return False, str(exc)

    try:
        client.ping()
    except MongodbAuthError as exc:
        return False, f"Autenticación fallida: {exc}"
    except MongodbNetworkError as exc:
        return False, f"Error de red: {exc}"
    except MongodbDataError as exc:
        return False, f"Error de datos: {exc}"
    except Exception as exc:  # red de seguridad: jamás propagar
        return False, f"Error inesperado: {exc}"

    return (
        True,
        f"Conexión exitosa a {client.config.host}:{client.config.port}/"
        f"{client.config.database}",
    )


if __name__ == "__main__":
    ok, message = test_connection()
    print(f"{'OK' if ok else 'FALLO'}: {message}")
    raise SystemExit(0 if ok else 1)
