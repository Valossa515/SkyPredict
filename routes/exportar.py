from flask import Blueprint, request, send_file
import pandas as pd
import io
from services.weather_service import carregar_dados
from services.validators import validar_coordenadas

exportar_bp = Blueprint('exportar', __name__)

@exportar_bp.route('/exportar_excel', methods=['GET'])
def exportar_excel():
    lat, lon = validar_coordenadas(request.args.get('lat'), request.args.get('lon'))

    df = carregar_dados(lat, lon)
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=True, sheet_name='Dados')

    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='dados_meteorologicos.xlsx'
    )
