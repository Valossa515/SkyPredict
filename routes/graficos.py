from flask import Blueprint, request, jsonify, send_file
import pandas as pd
import matplotlib.pyplot as plt
import io
from datetime import datetime
from services.meteostat_service import carregar_dados
from services.model_service import prever_variavel
from config import HISTORICAL_LABEL, FUTURE_DATE_LABEL, PREDICTION_LABEL, TEMPERATURE_UNIT

graficos_bp = Blueprint('graficos', __name__)

@graficos_bp.route('/graficos', methods=['GET'])
def graficos():
    data_futura = request.args.get('data')
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)

    if not lat or not lon or not data_futura:
        return jsonify({"erro": "Os parâmetros 'lat', 'lon' e 'data' são obrigatórios."}), 400

    try:
        datetime.strptime(data_futura, '%Y-%m-%d')
        df, _ = carregar_dados(lat, lon)

        previsoes = {coluna: prever_variavel(df, coluna, data_futura) for coluna in ['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']}

        plt.figure(figsize=(15, 10))

        for i, (coluna, unidade) in enumerate(zip(['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres'], 
                                                  [TEMPERATURE_UNIT, TEMPERATURE_UNIT, TEMPERATURE_UNIT, 'Precipitação (mm)', 'Velocidade do Vento (m/s)', 'Pressão (hPa)'])):
            plt.subplot(3, 2, i + 1)
            plt.plot(df.index, df[coluna], label=HISTORICAL_LABEL)
            plt.axvline(pd.to_datetime(data_futura), color='red', linestyle='--', label=FUTURE_DATE_LABEL)
            plt.scatter(pd.to_datetime(data_futura), previsoes[coluna], color='green', label=PREDICTION_LABEL)
            plt.title(coluna.upper())
            plt.xlabel('Data')
            plt.ylabel(unidade)
            plt.legend()

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()

        return send_file(buf, mimetype='image/png')

    except Exception as e:
        return jsonify({"erro": str(e)}), 500
