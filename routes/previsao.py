from flask import Blueprint, request, jsonify
from services.meteostat_service import carregar_dados
from services.model_service import treinar_modelo, prever_variavel
import pandas as pd
from datetime import datetime

previsao_bp = Blueprint('previsao', __name__)

@previsao_bp.route('/previsao', methods=['GET'])
def previsao():
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    data_futura = request.args.get('data')

    if not lat or not lon or not data_futura:
        return jsonify({"erro": "Os parâmetros 'lat', 'lon' e 'data' são obrigatórios."}), 400

    try:
        datetime.strptime(data_futura, '%Y-%m-%d')
        df = carregar_dados(lat, lon)
        model = treinar_modelo(df)
        previsoes = {coluna: prever_variavel(df, coluna, data_futura) for coluna in ['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']}
        dados_futuros = pd.DataFrame(previsoes, index=[0])
        previsao_risco = model.predict(dados_futuros)[0]

        return jsonify({
            "localizacao": {"latitude": lat, "longitude": lon},
            "data": data_futura,
            "previsao": previsoes,
            "risco": "Alto" if previsao_risco == 1 else "Baixo"
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
