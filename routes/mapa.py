from flask import Blueprint, request, jsonify, send_file
import folium
from io import BytesIO
from folium.plugins import AntPath
import requests
from config import AERO_API_URL, AEROAPI_HEADERS
import math

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

        # Obter coordenadas dos aeroportos
        lat_origem, lon_origem = obter_coordenadas_aeroporto(origem)
        lat_destino, lon_destino = obter_coordenadas_aeroporto(destino)

        # Criar um mapa centrado na origem
        mapa = folium.Map(location=[lat_origem, lon_origem], zoom_start=5)

        # Adicionar marcadores para origem e destino
        folium.Marker([lat_origem, lon_origem], popup=f'Origem: {origem}').add_to(mapa)
        folium.Marker([lat_destino, lon_destino], popup=f'Destino: {destino}').add_to(mapa)

        # Adicionar uma linha entre origem e destino
        folium.PolyLine(locations=[[lat_origem, lon_origem], [lat_destino, lon_destino]], color='blue').add_to(mapa)

        # Adicionar informações de risco ao mapa
        risco_origem = sugestao_data['risco_origem']
        risco_destino = sugestao_data['risco_destino']
        sugestao = sugestao_data['sugestao']

        folium.Marker(
            [lat_origem, lon_origem],
            popup=f"Risco na Origem: {risco_origem}\nSugestão: {sugestao}",
            icon=folium.Icon(color='red' if risco_origem == "Alto" else 'green')
        ).add_to(mapa)

        folium.Marker(
            [lat_destino, lon_destino],
            popup=f"Risco no Destino: {risco_destino}\nSugestão: {sugestao}",
            icon=folium.Icon(color='red' if risco_destino == "Alto" else 'green')
        ).add_to(mapa)

        # Adicionar animação de um "aviãozinho" se movendo da origem ao destino
        ant_path = AntPath(
            locations=[[lat_origem, lon_origem], [lat_destino, lon_destino]],
            color='red',
            weight=5,
            dash_array=[10, 20],
            delay=1000,  # Atraso entre cada segmento da animação (em ms)
            pulse_color='blue'  # Cor do efeito de pulsação
        )
        ant_path.add_to(mapa)

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