"""Configuración del conector leída desde variables de entorno.

Convención de la plataforma: cada campo del formulario de configuración
llega como variable de entorno {ENV_PREFIX}{CAMPO} en mayúsculas.
Para este conector el prefijo es RUVIC_MONGODB_.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

ENV_PREFIX = "RUVIC_MONGODB_"

_TRUE_VALUES = {"1", "true", "yes", "on"}


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in _TRUE_VALUES


@dataclass(frozen=True)
class MongodbConfig:
    """Parámetros de conexión a MongoDB.

    use_srv=True (recomendado para MongoDB Atlas y la mayoría de
    proveedores gestionados) usa el esquema mongodb+srv://, que
    resuelve host y puertos reales del cluster vía DNS SRV — en ese
    caso `port` se ignora, tal como exige el driver oficial.
    use_srv=False es para instancias autoalojadas/standalone con
    conexión directa host:port.
    """

    host: str
    port: int
    database: str
    username: str
    password: str
    auth_source: str
    use_srv: bool = False
    connect_timeout: int = 10

    @classmethod
    def from_env(cls) -> MongodbConfig:
        """Construye la configuración desde las variables RUVIC_MONGODB_*.

        Raises:
            ValueError: si falta alguna variable obligatoria.

        Ejemplo:
            >>> config = MongodbConfig.from_env()
            >>> config.host
            'db.empresa.com'
        """
        missing = [
            f"{ENV_PREFIX}{name}"
            for name in ("HOST", "DATABASE", "USERNAME", "PASSWORD")
            if not os.environ.get(f"{ENV_PREFIX}{name}")
        ]
        if missing:
            raise ValueError(
                "Faltan variables de entorno del conector mongodb: "
                + ", ".join(missing)
                + ". Configura el conector en Settings → Conectores."
            )
        database = os.environ[f"{ENV_PREFIX}DATABASE"]
        return cls(
            host=os.environ[f"{ENV_PREFIX}HOST"],
            port=int(os.environ.get(f"{ENV_PREFIX}PORT", "27017")),
            database=database,
            username=os.environ[f"{ENV_PREFIX}USERNAME"],
            password=os.environ[f"{ENV_PREFIX}PASSWORD"],
            auth_source=os.environ.get(f"{ENV_PREFIX}AUTH_SOURCE", database),
            use_srv=_as_bool(os.environ.get(f"{ENV_PREFIX}USE_SRV"), False),
            connect_timeout=int(os.environ.get(f"{ENV_PREFIX}CONNECT_TIMEOUT", "10")),
        )
