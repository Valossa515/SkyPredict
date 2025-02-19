from flask import Blueprint, request, jsonify
from services.aeroapi_service import obter_coordenadas_aeroporto, obter_rotas_aeroporto
from services.meteostat_service import carregar_dados
from services.model_service import treinar_modelo, prever_variavel
import pandas as pd
from datetime import datetime
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
        # Validação da data
        datetime.strptime(data_futura, '%Y-%m-%d')

        # Obter coordenadas dos aeroportos
        lat_origem, lon_origem = obter_coordenadas_aeroporto(origem_id)
        lat_destino, lon_destino = obter_coordenadas_aeroporto(destino_id)

        # Carregar dados da origem e treinar modelo
        df_origem = carregar_dados(lat_origem, lon_origem)
        model_origem = treinar_modelo(df_origem)

        # Fazer previsão para a origem
        previsoes_origem = {coluna: prever_variavel(df_origem, coluna, data_futura) for coluna in ['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']}
        risco_origem = model_origem.predict(pd.DataFrame(previsoes_origem, index=[0]))[0]

        # Carregar dados do destino e treinar modelo
        df_destino = carregar_dados(lat_destino, lon_destino)
        model_destino = treinar_modelo(df_destino)

        # Fazer previsão para o destino
        previsoes_destino = {coluna: prever_variavel(df_destino, coluna, data_futura) for coluna in ['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']}
        risco_destino = model_destino.predict(pd.DataFrame(previsoes_destino, index=[0]))[0]

        # Obter rotas entre origem e destino
        rotas = obter_rotas_aeroporto(origem_id, destino_id)

        # Definir a sugestão de rota com base nos riscos
        if risco_origem == 1 or risco_destino == 1:
            sugestao = "Evitar voo devido a alto risco meteorológico."
        else:
            sugestao = "Rota segura. Risco meteorológico baixo."

        # Retornar resposta
        sugestao_rota = {
            "origem": origem_id,
            "destino": destino_id,
            "data": data_futura,
            "risco_origem": "Alto" if risco_origem == 1 else "Baixo",
            "risco_destino": "Alto" if risco_destino == 1 else "Baixo",
            "rotas": rotas,
            "sugestao": sugestao
        }
        
        result = collection.insert_one(sugestao_rota)
        sugestao_rota["_id"] = str(result.inserted_id)
        
        return jsonify(sugestao_rota)
        
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
