from flask import Blueprint, request, jsonify, Response
import folium
from services.aeroapi_service import obter_coordenadas_aeroporto
from services.rota_service import gerar_sugestao_rota

mapa_bp = Blueprint('mapa', __name__)

def _extract_lat_lon(aeroapi_result):
    """
    Aceita:
      - (lat, lon) / [lat, lon]
      - dict JSON da AeroAPI
    Retorna: (lat, lon) como float
    """
    # Caso 1: já veio como tupla/lista
    if isinstance(aeroapi_result, (tuple, list)) and len(aeroapi_result) >= 2:
        return float(aeroapi_result[0]), float(aeroapi_result[1])

    # Caso 2: veio como dict JSON
    if isinstance(aeroapi_result, dict):
        # tenta vários padrões comuns
        for lat_key, lon_key in [
            ("latitude", "longitude"),
            ("lat", "lon"),
            ("lat", "lng"),
            ("Latitude", "Longitude"),
        ]:
            if lat_key in aeroapi_result and lon_key in aeroapi_result:
                return float(aeroapi_result[lat_key]), float(aeroapi_result[lon_key])

        # alguns providers colocam dentro de "location"
        loc = aeroapi_result.get("location") if "location" in aeroapi_result else None
        if isinstance(loc, dict):
            for lat_key, lon_key in [
                ("latitude", "longitude"),
                ("lat", "lon"),
                ("lat", "lng"),
            ]:
                if lat_key in loc and lon_key in loc:
                    return float(loc[lat_key]), float(loc[lon_key])

    raise ValueError(
        f"Não foi possível extrair latitude/longitude do retorno da AeroAPI. Tipo={type(aeroapi_result)}"
    )

@mapa_bp.route('/mapa_sugerido', methods=['GET'])
def mostrar_mapa_sugerido_animado_html():
    origem_id = request.args.get('origem_id')
    destino_id = request.args.get('destino_id')
    data_futura = request.args.get('data')

    if not origem_id or not destino_id or not data_futura:
        return jsonify({"erro": "Os parâmetros 'origem_id', 'destino_id' e 'data' são obrigatórios."}), 400

    try:
        sugestao_data = gerar_sugestao_rota(origem_id, destino_id, data_futura)

        origem = sugestao_data['origem']
        destino = sugestao_data['destino']
        rotas = sugestao_data['rotas']
        risco_origem = sugestao_data['risco_origem']
        risco_destino = sugestao_data['risco_destino']
        sugestao = sugestao_data['sugestao']

        # Obter coordenadas dos aeroportos (corrigido)
        origem_info = obter_coordenadas_aeroporto(origem)
        destino_info = obter_coordenadas_aeroporto(destino)
        lat_origem, lon_origem = _extract_lat_lon(origem_info)
        lat_destino, lon_destino = _extract_lat_lon(destino_info)

        # Criar o mapa
        mapa = folium.Map(location=[lat_origem, lon_origem], zoom_start=5)

        # Marcadores origem/destino
        folium.Marker(
            [lat_origem, lon_origem],
            popup=f"Origem: {origem}<br>Risco: {risco_origem}<br>Sugestão: {sugestao}",
            icon=folium.Icon(color='red' if risco_origem == "Alto" else 'green')
        ).add_to(mapa)

        folium.Marker(
            [lat_destino, lon_destino],
            popup=f"Destino: {destino}<br>Risco: {risco_destino}<br>Sugestão: {sugestao}",
            icon=folium.Icon(color='red' if risco_destino == "Alto" else 'green')
        ).add_to(mapa)

        # Linha GeoJSON
        geojson_data = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [lon_origem, lat_origem],
                    [lon_destino, lat_destino]
                ]
            },
            "properties": {"tooltip": f"Origem: {origem} ➡️ Destino: {destino}"}
        }

        folium.GeoJson(
            geojson_data,
            style_function=lambda x: {"color": "blue", "weight": 5, "dashArray": "5, 10"},
            tooltip=folium.Tooltip(geojson_data["properties"]["tooltip"]),
            popup=folium.Popup(f"Rota de {origem} para {destino}")
        ).add_to(mapa)

        # Rotas (marcador na origem só pra exibir detalhes)
        routes_list = rotas.get("routes", []) if isinstance(rotas, dict) else []
        for rota in routes_list:
            popup_content = f"""
                <b>Tipo de Aeronave:</b> {', '.join(rota.get('aircraft_types', []))}<br>
                <b>Altitude:</b> {rota.get('filed_altitude_min', '-') } - {rota.get('filed_altitude_max', '-') } ft<br>
                <b>Distância:</b> {rota.get('route_distance', '-') }<br>
                <b>Última Partida:</b> {rota.get('last_departure_time', '-') }<br>
                <b>Rota:</b> {rota.get('route', '-') }
            """
            folium.Marker(
                [lat_origem, lon_origem],
                popup=folium.Popup(popup_content, max_width=300),
                icon=folium.Icon(color='orange', icon='plane', prefix='fa')
            ).add_to(mapa)

        # ✅ Retorna HTML de verdade com content-type correto (recomendação)
        html = mapa.get_root().render()
        return Response(html, mimetype="text/html")

    except Exception as e:
        return jsonify({"erro": str(e)}), 500
