import logging

from flask import Blueprint, request, jsonify
from pymongo.errors import PyMongoError

from services.rota_service import gerar_sugestao_rota
from services.mongo_service import get_collection
from services.validators import validar_data

logger = logging.getLogger(__name__)

sugerir_rota_bp = Blueprint('sugerir_rota', __name__)


@sugerir_rota_bp.route('/sugerir_rota', methods=['GET'])
def sugerir_rota():
    origem_id = request.args.get('origem_id')
    destino_id = request.args.get('destino_id')
    data_futura = request.args.get('data')

    if not origem_id or not destino_id or not data_futura:
        return jsonify({"erro": "Os parâmetros 'origem_id', 'destino_id' e 'data' são obrigatórios."}), 400

    validar_data(data_futura)

    try:
        collection = get_collection()
        sugestao_rota = gerar_sugestao_rota(origem_id, destino_id, data_futura)

        result = collection.insert_one(sugestao_rota)
        sugestao_rota["_id"] = str(result.inserted_id)

        return jsonify(sugestao_rota)

    except ValueError as e:
        # Erros de configuração/validação (ex.: env var ausente, ID inválido).
        logger.error("Erro de validação/configuração ao sugerir rota: %s", e)
        return jsonify({"erro": str(e)}), 400
    except PyMongoError:
        logger.exception("Falha ao conectar ou operar no MongoDB.")
        return jsonify({"erro": "Falha ao conectar ou operar no MongoDB."}), 500
