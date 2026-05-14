"""Dependências injetáveis da API."""

from functools import lru_cache

import config
from logger import RunLogger


@lru_cache(maxsize=1)
def get_logger() -> RunLogger:
    """Singleton — uma conexão sqlite reutilizada entre requests.

    Em testes, chame `get_logger.cache_clear()` no fixture pra forçar
    nova instância apontando pro tmp_path.
    """
    return RunLogger(config.MMB_DB_PATH)
