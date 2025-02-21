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
        df = carregar_dados(lat, lon)

        previsoes = {coluna: prever_variavel(df, coluna, data_futura) for coluna in ['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']}

        fig, axes = plt.subplots(3, 2, figsize=(15, 10)) 
        axes = axes.flatten()

        colunas = ['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']
        unidades = [TEMPERATURE_UNIT, TEMPERATURE_UNIT, TEMPERATURE_UNIT, 'Precipitação (mm)', 'Velocidade do Vento (m/s)', 'Pressão (hPa)']

        for i, (coluna, unidade) in enumerate(zip(colunas, unidades)):
            ax = axes[i]
            ax.plot(df.index, df[coluna], label=HISTORICAL_LABEL)
            ax.axvline(pd.to_datetime(data_futura), color='red', linestyle='--', label=FUTURE_DATE_LABEL)
            ax.scatter(pd.to_datetime(data_futura), previsoes[coluna], color='green', label=PREDICTION_LABEL)
            ax.set_title(coluna.upper())
            ax.set_xlabel('Data')
            ax.set_ylabel(unidade)
            ax.legend(loc='upper left', bbox_to_anchor=(1, 1))

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        plt.close()

        return send_file(buf, mimetype='image/png')

    except Exception as e:
        return jsonify({"erro": str(e)}), 500
