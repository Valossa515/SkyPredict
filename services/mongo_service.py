"""Acesso ao MongoDB com cliente reutilizável (lazy singleton).

Evita abrir uma nova conexão a cada request — o driver do PyMongo já
gerencia um pool de conexões internamente quando o cliente é reutilizado.
"""
import os
import threading

from pymongo import MongoClient

_client = None
_lock = threading.Lock()


def _validar_config():
    mongo_uri = os.getenv("MONGO_URI")
    mongo_db = os.getenv("MONGOD_DB")
    mongo_collection = os.getenv("MONGO_COLLECTION")

    missing_vars = [
        name
        for name, value in (
            ("MONGO_URI", mongo_uri),
            ("MONGOD_DB", mongo_db),
            ("MONGO_COLLECTION", mongo_collection),
        )
        if not value
    ]
    if missing_vars:
        missing_list = ", ".join(missing_vars)
        raise ValueError(
            f"Variáveis de ambiente ausentes: {missing_list}. Configure-as e tente novamente."
        )
    return mongo_uri, mongo_db, mongo_collection


def get_collection():
    """Retorna a coleção configurada, criando o cliente sob demanda uma única vez."""
    global _client
    mongo_uri, mongo_db, mongo_collection = _validar_config()

    if _client is None:
        with _lock:
            if _client is None:
                _client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)

    return _client[mongo_db][mongo_collection]
