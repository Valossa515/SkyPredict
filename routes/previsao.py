from flask import Blueprint, request, jsonify
from services.meteostat_service import carregar_dados
from services.model_service import treinar_modelo, prever_variavel, prever_com_modelo, BASE_FEATURES
from datetime import datetime
import numpy as np

previsao_bp = Blueprint('previsao', __name__)


def _to_python_type(val):
    """Converte valores numpy para tipos Python nativos."""
    if isinstance(val, (np.integer, np.int64, np.int32)):
        return int(val)
    elif isinstance(val, (np.floating, np.float64, np.float32)):
        return float(val)
    elif isinstance(val, np.bool_):
        return bool(val)
    return val


@previsao_bp.route('/previsao', methods=['GET'])
def previsao():
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    data_futura = request.args.get('data')

    if lat is None or lon is None or not data_futura:
        return jsonify({"erro": "Os parâmetros 'lat', 'lon' e 'data' são obrigatórios."}), 400

    try:
        datetime.strptime(data_futura, '%Y-%m-%d')
        df = carregar_dados(lat, lon)
        model = treinar_modelo(df, lat, lon)
        previsoes = {
            coluna: _to_python_type(prever_variavel(df, coluna, data_futura, lat, lon))
            for coluna in BASE_FEATURES
        }

        # Usar a função prever_com_modelo que aplica as transformações corretas
        previsao_risco = prever_com_modelo(previsoes, model, lat, lon, data_futura)[0]

        return jsonify({
            "localizacao": {"latitude": lat, "longitude": lon},
            "data": data_futura,
            "previsao": previsoes,
            "risco": "Alto" if previsao_risco == 1 else "Baixo"
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
