"""Excepciones propias del conector MongoDB.

Separan los tres tipos de fallo que el usuario debe distinguir:
autenticación, red/servidor y datos. Nunca exponemos excepciones
crípticas del driver subyacente.
"""


class MongodbConnectorError(Exception):
    """Error base del conector."""


class MongodbAuthError(MongodbConnectorError):
    """Credenciales inválidas o permisos insuficientes."""


class MongodbNetworkError(MongodbConnectorError):
    """No se pudo alcanzar el servidor (host/puerto/red/timeout)."""


class MongodbDataError(MongodbConnectorError):
    """La operación es válida pero el objeto no existe o el filtro es inválido."""
