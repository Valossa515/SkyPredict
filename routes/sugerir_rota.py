from flask import Blueprint, request, jsonify
from services.rota_service import gerar_sugestao_rota
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')
MONGO_DB = os.getenv('MONGOD_DATASET')
MONGO_COLLECTION = os.getenv('MONGO_COLLECTION')

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
collection = db[MONGO_COLLECTION]

sugerir_rota_bp = Blueprint('sugerir_rota', __name__)

@sugerir_rota_bp.route('/sugerir_rota', methods=['GET'])
def sugerir_rota():
    origem_id = request.args.get('origem_id')
    destino_id = request.args.get('destino_id')
    data_futura = request.args.get('data')

    if not origem_id or not destino_id or not data_futura:
        return jsonify({"erro": "Os parâmetros 'origem_id', 'destino_id' e 'data' são obrigatórios."}), 400

    try:
        sugestao_rota = gerar_sugestao_rota(origem_id, destino_id, data_futura)
        
        result = collection.insert_one(sugestao_rota)
        sugestao_rota["_id"] = str(result.inserted_id)
        
        return jsonify(sugestao_rota)
        
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
