"""Cliente de solo lectura para MongoDB.

Capacidades:
- list_collections():    listar colecciones de la base de datos.
- read_documents():      leer documentos de una colección con filtro y límite.
- count_documents():     contar documentos que cumplen un filtro.
- collection_stats():    estadísticas de una colección (documentos, tamaño, índices).

Las credenciales SIEMPRE provienen de variables de entorno RUVIC_MONGODB_*
(ver config.MongodbConfig.from_env). Prohibido hardcodearlas.

El conector nunca invoca operaciones de escritura (insert/update/delete):
solo emite comandos de lectura (find, count_documents, collStats, etc.).
"""

from __future__ import annotations

import datetime
import re
from typing import Any
from urllib.parse import quote_plus

from bson import ObjectId
from pymongo import MongoClient as _PyMongoClient
from pymongo.errors import (
    ConnectionFailure,
    OperationFailure,
    PyMongoError,
    ServerSelectionTimeoutError,
)

from .config import MongodbConfig
from .exceptions import (
    MongodbAuthError,
    MongodbConnectorError,
    MongodbDataError,
    MongodbNetworkError,
)
from .logging_utils import get_logger

_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

_AUTH_CODE_NAMES = {"AuthenticationFailed", "Unauthorized"}
_NAMESPACE_NOT_FOUND_CODE = 26  # NamespaceNotFound

# Operadores que permiten ejecutar JavaScript arbitrario en el servidor
# (server-side JS). Un filtro de solo lectura nunca debería necesitarlos;
# se bloquean sin importar en qué nivel de anidamiento aparezcan.
_JS_EXECUTION_OPERATORS = {"$where", "$function", "$accumulator"}


def _validate_name(name: str, kind: str) -> None:
    """Valida nombres de colección/base de datos (sin '$' ni caracteres de control)."""
    if not name or not _NAME_RE.match(name):
        raise MongodbDataError(
            f"Nombre de {kind} inválido: {name!r}. "
            "Solo se permiten letras, números, guion, guion bajo y punto."
        )


def _validate_filter(value: Any) -> None:
    """Recorre el filtro recursivamente y rechaza cualquier operador que
    ejecute JavaScript en el servidor ($where, $function, $accumulator),
    sin importar en qué nivel de anidamiento aparezca."""
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in _JS_EXECUTION_OPERATORS:
                raise MongodbDataError(
                    f"El operador {key!r} ejecuta JavaScript en el servidor y "
                    "está prohibido en este conector de solo lectura."
                )
            _validate_filter(nested)
    elif isinstance(value, list):
        for item in value:
            _validate_filter(item)


def _serialize(value: Any) -> Any:
    """Convierte tipos de BSON no serializables (ObjectId, datetime) a texto,
    recursivamente sobre dicts y listas."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    return value


def _human_size(num_bytes: int | None) -> str:
    """Convierte bytes a un tamaño legible (ej. "12 MB")."""
    if not num_bytes:
        return "0 B"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _wrap_operation_error(exc: OperationFailure, not_found_message: str) -> MongodbConnectorError:
    """Traduce un error de operación de MongoDB a una excepción propia, sin
    dejar escapar nunca el tipo crudo del driver."""
    details = getattr(exc, "details", None) or {}
    code_name = details.get("codeName")
    if code_name in _AUTH_CODE_NAMES or getattr(exc, "code", None) == 13:
        return MongodbAuthError(
            "El usuario no tiene permiso de lectura sobre esa base de datos o "
            "colección. Revisa el rol asignado en el servidor."
        )
    if getattr(exc, "code", None) == _NAMESPACE_NOT_FOUND_CODE:
        return MongodbDataError(not_found_message)
    return MongodbDataError(f"Error de datos: {exc}")


class MongodbClient:
    """Cliente de solo lectura para MongoDB.

    Args:
        config: configuración de conexión. Si se omite, se lee de las
            variables de entorno RUVIC_MONGODB_* (comportamiento estándar
            en el runtime de la plataforma).

    Ejemplo:
        >>> client = MongodbClient()        # lee RUVIC_MONGODB_* del entorno
        >>> client.list_collections()
        [{'collection': 'clientes', 'documents_estimate': 1520}]
    """

    def __init__(self, config: MongodbConfig | None = None) -> None:
        self.config = config or MongodbConfig.from_env()
        self._logger = get_logger()
        self._client: _PyMongoClient | None = None

    # ------------------------------------------------------------------ #
    # Conexión
    # ------------------------------------------------------------------ #

    def _get_client(self) -> _PyMongoClient:
        if self._client is not None:
            return self._client
        if self.config.use_srv:
            # mongodb+srv:// (MongoDB Atlas y la mayoría de proveedores
            # gestionados): el driver resuelve host y puertos reales del
            # cluster vía DNS SRV, así que NO se pasa `port`.
            uri = (
                f"mongodb+srv://{quote_plus(self.config.username)}:"
                f"{quote_plus(self.config.password)}@{self.config.host}/"
                f"?authSource={quote_plus(self.config.auth_source)}"
            )
            self._client = _PyMongoClient(
                uri,
                serverSelectionTimeoutMS=self.config.connect_timeout * 1000,
                connectTimeoutMS=self.config.connect_timeout * 1000,
            )
        else:
            # Instancia autoalojada/standalone: conexión directa host:port.
            self._client = _PyMongoClient(
                host=self.config.host,
                port=self.config.port,
                username=self.config.username,
                password=self.config.password,
                authSource=self.config.auth_source,
                serverSelectionTimeoutMS=self.config.connect_timeout * 1000,
                connectTimeoutMS=self.config.connect_timeout * 1000,
            )
        return self._client

    def _get_database(self):
        client = self._get_client()
        return client[self.config.database]

    def ping(self) -> bool:
        """Verifica la conexión con el comando `ping`.

        Returns:
            True si la conexión funciona.

        Raises:
            MongodbAuthError / MongodbNetworkError / MongodbDataError según el fallo.
        """
        try:
            self._get_client().admin.command("ping")
        except OperationFailure as exc:
            raise _wrap_operation_error(exc, "Comando ping fallido.") from exc
        except (ServerSelectionTimeoutError, ConnectionFailure) as exc:
            raise MongodbNetworkError(
                f"No se pudo conectar a {self.config.host}:{self.config.port} "
                f"(timeout {self.config.connect_timeout}s). Verifica host, puerto "
                "y acceso de red."
            ) from exc
        except PyMongoError as exc:
            raise MongodbDataError(f"Error inesperado del driver: {exc}") from exc
        self._logger.info("Ping exitoso a %s:%s", self.config.host, self.config.port)
        return True

    # ------------------------------------------------------------------ #
    # Capacidad 1: listar colecciones
    # ------------------------------------------------------------------ #

    def list_collections(self) -> list[dict[str, Any]]:
        """Lista las colecciones de la base de datos con su conteo estimado
        de documentos.

        Returns:
            Lista de dicts: {"collection", "documents_estimate"}.

        Ejemplo:
            >>> client.list_collections()
            [{'collection': 'ventas', 'documents_estimate': 89123}]
        """
        db = self._get_database()
        try:
            names = db.list_collection_names()
            result = [
                {"collection": name, "documents_estimate": db[name].estimated_document_count()}
                for name in sorted(names)
            ]
        except OperationFailure as exc:
            raise _wrap_operation_error(
                exc, f"La base de datos {self.config.database!r} no existe o no es accesible."
            ) from exc
        except (ServerSelectionTimeoutError, ConnectionFailure) as exc:
            raise MongodbNetworkError(f"No se pudo listar colecciones: {exc}") from exc
        self._logger.info(
            "Se listaron %d colecciones de %s", len(result), self.config.database
        )
        return result

    # ------------------------------------------------------------------ #
    # Capacidad 2: leer documentos con filtro
    # ------------------------------------------------------------------ #

    def read_documents(
        self,
        collection: str,
        filter: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Lee documentos de una colección que cumplan un filtro.

        Args:
            collection: nombre de la colección.
            filter: filtro estilo MongoDB (mismo formato de `find()`).
                Vacío o None trae todos los documentos (hasta el límite).
            limit: máximo de documentos a retornar (default 100, máximo 10000).

        Returns:
            Lista de dicts (cada documento, con `_id` y fechas serializados
            como texto).

        Ejemplo:
            >>> client.read_documents("clientes", {"ciudad": "Bogota"}, limit=5)
            [{'_id': '64f...', 'nombre': 'ACME', 'ciudad': 'Bogota'}, ...]
        """
        _validate_name(collection, "colección")
        if filter is not None and not isinstance(filter, dict):
            raise MongodbDataError("filter debe ser un dict (o None).")
        _validate_filter(filter)
        try:
            limit = max(1, min(int(limit), 10_000))
        except (TypeError, ValueError) as exc:
            raise MongodbDataError(
                f"limit inválido: {limit!r}. Debe ser un número entero."
            ) from exc
        db = self._get_database()
        try:
            cursor = db[collection].find(filter or {}).limit(limit)
            rows = [_serialize(doc) for doc in cursor]
        except OperationFailure as exc:
            raise _wrap_operation_error(
                exc, f'La colección "{collection}" no existe.'
            ) from exc
        except (ServerSelectionTimeoutError, ConnectionFailure) as exc:
            raise MongodbNetworkError(f"No se pudo leer la colección: {exc}") from exc
        self._logger.info(
            'Leídos %d documentos de "%s" (limit=%d)', len(rows), collection, limit
        )
        return rows

    # ------------------------------------------------------------------ #
    # Capacidad 3: contar documentos
    # ------------------------------------------------------------------ #

    def count_documents(
        self, collection: str, filter: dict[str, Any] | None = None
    ) -> int:
        """Cuenta los documentos de una colección que cumplan un filtro
        (conteo exacto, no estimado).

        Args:
            collection: nombre de la colección.
            filter: filtro estilo MongoDB. Vacío o None cuenta todos los
                documentos.

        Returns:
            Número de documentos que cumplen el filtro.

        Ejemplo:
            >>> client.count_documents("clientes", {"ciudad": "Bogota"})
            342
        """
        _validate_name(collection, "colección")
        if filter is not None and not isinstance(filter, dict):
            raise MongodbDataError("filter debe ser un dict (o None).")
        _validate_filter(filter)
        db = self._get_database()
        try:
            count = db[collection].count_documents(filter or {})
        except OperationFailure as exc:
            raise _wrap_operation_error(
                exc, f'La colección "{collection}" no existe.'
            ) from exc
        except (ServerSelectionTimeoutError, ConnectionFailure) as exc:
            raise MongodbNetworkError(f"No se pudo contar documentos: {exc}") from exc
        self._logger.info('Contados %d documentos en "%s"', count, collection)
        return count

    # ------------------------------------------------------------------ #
    # Capacidad 4: estadísticas de una colección
    # ------------------------------------------------------------------ #

    def collection_stats(self, collection: str) -> dict[str, Any]:
        """Obtiene estadísticas de una colección.

        Args:
            collection: nombre de la colección.

        Returns:
            Dict con: document_count (exacto), total_size (legible, ej.
            "12 MB"), avg_document_size (bytes) e indexes (lista de nombres).

        Ejemplo:
            >>> client.collection_stats("ventas")
            {'document_count': 89123, 'total_size': '12.0 MB', ...}
        """
        _validate_name(collection, "colección")
        db = self._get_database()
        try:
            stats = db.command("collStats", collection)
            index_names = list(db[collection].index_information().keys())
        except OperationFailure as exc:
            raise _wrap_operation_error(
                exc, f'La colección "{collection}" no existe.'
            ) from exc
        except (ServerSelectionTimeoutError, ConnectionFailure) as exc:
            raise MongodbNetworkError(f"No se pudieron obtener estadísticas: {exc}") from exc
        return {
            "collection": collection,
            "document_count": stats.get("count", 0),
            "total_size": _human_size(stats.get("size")),
            "storage_size": _human_size(stats.get("storageSize")),
            "avg_document_size": stats.get("avgObjSize", 0),
            "indexes": index_names,
        }
