"""Conector Ruvic de solo lectura para MongoDB."""

from .client import MongodbClient
from .config import ENV_PREFIX, MongodbConfig
from .exceptions import (
    MongodbAuthError,
    MongodbConnectorError,
    MongodbDataError,
    MongodbNetworkError,
)
from .logging_utils import setup_logging

__all__ = [
    "ENV_PREFIX",
    "MongodbAuthError",
    "MongodbClient",
    "MongodbConfig",
    "MongodbConnectorError",
    "MongodbDataError",
    "MongodbNetworkError",
    "setup_logging",
]

__version__ = "1.0.0"
