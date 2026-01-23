from flask import Blueprint, request, jsonify
from services.rota_service import gerar_sugestao_rota
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from dotenv import load_dotenv
import os
import logging

load_dotenv()

logger = logging.getLogger(__name__)

sugerir_rota_bp = Blueprint('sugerir_rota', __name__)

def _get_mongo_collection():
    mongo_uri = os.getenv('MONGO_URI')
    mongo_db = os.getenv('MONGOD_DATASET')
    mongo_collection = os.getenv('MONGO_COLLECTION')

    missing_vars = [
        name
        for name, value in (
            ("MONGO_URI", mongo_uri),
            ("MONGOD_DATASET", mongo_db),
            ("MONGO_COLLECTION", mongo_collection),
        )
        if not value
    ]
    if missing_vars:
        missing_list = ", ".join(missing_vars)
        raise ValueError(
            f"Variáveis de ambiente ausentes: {missing_list}. Configure-as e tente novamente."
        )

    client = MongoClient(mongo_uri)
    db = client[mongo_db]
    return db[mongo_collection]

@sugerir_rota_bp.route('/sugerir_rota', methods=['GET'])
def sugerir_rota():
    origem_id = request.args.get('origem_id')
    destino_id = request.args.get('destino_id')
    data_futura = request.args.get('data')

    if not origem_id or not destino_id or not data_futura:
        return jsonify({"erro": "Os parâmetros 'origem_id', 'destino_id' e 'data' são obrigatórios."}), 400

    try:
        collection = _get_mongo_collection()
        sugestao_rota = gerar_sugestao_rota(origem_id, destino_id, data_futura)
        
        result = collection.insert_one(sugestao_rota)
        sugestao_rota["_id"] = str(result.inserted_id)
        
        return jsonify(sugestao_rota)
        
    except ValueError as e:
        logger.error("Erro de configuração do MongoDB: %s", e)
        return jsonify({"erro": str(e)}), 500
    except PyMongoError as e:
        logger.exception("Falha ao conectar ou operar no MongoDB.")
        return jsonify({"erro": "Falha ao conectar ou operar no MongoDB."}), 500
    except Exception as e:
        logger.exception("Erro inesperado ao sugerir rota.")
        return jsonify({"erro": str(e)}), 500
