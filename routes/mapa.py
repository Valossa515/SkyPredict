from flask import Blueprint, request, jsonify, send_file
import folium
from io import BytesIO
from folium.plugins import AntPath
import requests
from config import AERO_API_URL, AEROAPI_HEADERS
import math
import json

mapa_bp = Blueprint('mapa', __name__)

@mapa_bp.route('/mapa_sugerido', methods=['GET'])
def mostrar_mapa_sugerido_animado_html():
    origem_id = request.args.get('origem_id')
    destino_id = request.args.get('destino_id')
    data_futura = request.args.get('data')

    if not origem_id or not destino_id or not data_futura:
        return jsonify({"erro": "Os parâmetros 'origem_id', 'destino_id' e 'data' são obrigatórios."}), 400

    try:
        # Chamar o endpoint /sugerir_rota internamente
        sugestao_url = f"http://localhost:5000/sugerir_rota?origem_id={origem_id}&destino_id={destino_id}&data={data_futura}"
        response = requests.get(sugestao_url)
        sugestao_data = response.json()

        if response.status_code != 200:
            return jsonify({"erro": "Erro ao obter sugestão de rota."}), 500

        # Extrair as coordenadas da sugestão de rota
        origem = sugestao_data['origem']
        destino = sugestao_data['destino']
        rotas = sugestao_data['rotas']
        risco_origem = sugestao_data['risco_origem']
        risco_destino = sugestao_data['risco_destino']
        sugestao = sugestao_data['sugestao']

        # Obter coordenadas dos aeroportos
        lat_origem, lon_origem = obter_coordenadas_aeroporto(origem)
        lat_destino, lon_destino = obter_coordenadas_aeroporto(destino)

        # Criar o mapa
        mapa = folium.Map(location=[lat_origem, lon_origem], zoom_start=5)

        # Adicionar marcadores para origem e destino com informações de risco
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

        # Criar um GeoJSON com a linha
        geojson_data = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [lon_origem, lat_origem],  # GeoJSON usa [longitude, latitude]
                    [lon_destino, lat_destino]
                ]
            },
            "properties": {
                "tooltip": f"Origem: {origem} ➡️ Destino: {destino}"
            }
        } 

        # Adicionar a linha ao mapa usando GeoJson
        folium.GeoJson(
            geojson_data,
            style_function=lambda x: {"color": "blue", "weight": 5, "dashArray": "5, 10"},
            tooltip=folium.Tooltip(geojson_data["properties"]["tooltip"]),
            popup=folium.Popup(f"Rota de {origem} para {destino}")
        ).add_to(mapa)

        # Adicionar informações sobre as rotas
        for rota in rotas['routes']:
            # Criar um popup com detalhes da rota
            popup_content = f"""
                <b>Tipo de Aeronave:</b> {', '.join(rota['aircraft_types'])}<br>
                <b>Altitude:</b> {rota['filed_altitude_min']} - {rota['filed_altitude_max']} ft<br>
                <b>Distância:</b> {rota['route_distance']}<br>
                <b>Última Partida:</b> {rota['last_departure_time']}<br>
                <b>Rota:</b> {rota['route']}
            """
            folium.Marker(
                [lat_origem, lon_origem],  # Pode ajustar para waypoints se disponíveis
                popup=folium.Popup(popup_content, max_width=300),
                icon=folium.Icon(color='orange', icon='plane', prefix='fa')
            ).add_to(mapa)

        # Retornar o mapa como uma página HTML
        return mapa._repr_html_()

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

def obter_coordenadas_aeroporto(aeroporto_id):
    url = f"{AERO_API_URL}/airports/{aeroporto_id}"
    response = requests.get(url, headers=AEROAPI_HEADERS)
    if response.status_code == 200:
        data = response.json()
        return data['latitude'], data['longitude']
    raise ValueError(f"Erro ao obter coordenadas do aeroporto {aeroporto_id}: {response.status_code}")