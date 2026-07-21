from flask import Blueprint, request, send_file
import pandas as pd
import matplotlib.pyplot as plt
import io
from services.weather_service import carregar_dados
from services.model_service import prever_variavel
from services.validators import validar_coordenadas, validar_data
from config import HISTORICAL_LABEL, FUTURE_DATE_LABEL, PREDICTION_LABEL, TEMPERATURE_UNIT, BASE_FEATURES

graficos_bp = Blueprint('graficos', __name__)

@graficos_bp.route('/graficos', methods=['GET'])
def graficos():
    lat, lon = validar_coordenadas(request.args.get('lat'), request.args.get('lon'))
    data_futura = validar_data(request.args.get('data'))

    df = carregar_dados(lat, lon)

    previsoes = {
        coluna: prever_variavel(df, coluna, data_futura, lat, lon)
        for coluna in BASE_FEATURES
    }

    fig, axes = plt.subplots(3, 2, figsize=(15, 10))
    axes = axes.flatten()

    unidades = [TEMPERATURE_UNIT, TEMPERATURE_UNIT, TEMPERATURE_UNIT, 'Precipitação (mm)', 'Velocidade do Vento (m/s)', 'Pressão (hPa)']

    try:
        for i, (coluna, unidade) in enumerate(zip(BASE_FEATURES, unidades)):
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
        return send_file(buf, mimetype='image/png')
    finally:
        plt.close(fig)
