"""Configuración del conector leída desde variables de entorno.

Convención de la plataforma: cada campo del formulario de configuración
llega como variable de entorno {ENV_PREFIX}{CAMPO} en mayúsculas.
Para este conector el prefijo es RUVIC_MONGODB_.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

ENV_PREFIX = "RUVIC_MONGODB_"


@dataclass(frozen=True)
class MongodbConfig:
    """Parámetros de conexión a MongoDB."""

    host: str
    port: int
    database: str
    username: str
    password: str
    auth_source: str
    connect_timeout: int = 10

    @classmethod
    def from_env(cls) -> "MongodbConfig":
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
            connect_timeout=int(os.environ.get(f"{ENV_PREFIX}CONNECT_TIMEOUT", "10")),
        )
