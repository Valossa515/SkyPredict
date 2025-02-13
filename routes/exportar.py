from flask import Blueprint, request, jsonify, send_file
import pandas as pd
import io
from services.meteostat_service import carregar_dados

exportar_bp = Blueprint('exportar', __name__)

@exportar_bp.route('/exportar_excel', methods=['GET'])
def exportar_excel():
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)

    if not lat or not lon:
        return jsonify({"erro": "Os parâmetros 'lat' e 'lon' são obrigatórios."}), 400

    try:
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

    except Exception as e:
        return jsonify({"erro": str(e)}), 500
