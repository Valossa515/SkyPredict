from flask import Blueprint, request, jsonify, Response
import folium

from services.aeroapi_service import obter_coordenadas_aeroporto
from services.rota_service import gerar_sugestao_rota
from services.geo_service import pontos_geodesicos, aeroportos_no_corredor, distancia_km
from services.validators import validar_data

mapa_bp = Blueprint('mapa', __name__)

# Corredor padrão (km) para considerar um aeroporto "no caminho".
_CORREDOR_PADRAO_KM = 400.0
# Máximo de aeroportos intermediários exibidos por padrão (os de menor desvio).
_LIMITE_PADRAO = 12


def _extract_lat_lon(aeroapi_result):
    """Aceita (lat, lon), lista, ou dict JSON da AeroAPI e retorna (lat, lon) float."""
    if isinstance(aeroapi_result, (tuple, list)) and len(aeroapi_result) >= 2:
        return float(aeroapi_result[0]), float(aeroapi_result[1])

    if isinstance(aeroapi_result, dict):
        for lat_key, lon_key in [("latitude", "longitude"), ("lat", "lon"), ("lat", "lng"), ("Latitude", "Longitude")]:
            if lat_key in aeroapi_result and lon_key in aeroapi_result:
                return float(aeroapi_result[lat_key]), float(aeroapi_result[lon_key])
        loc = aeroapi_result.get("location") if "location" in aeroapi_result else None
        if isinstance(loc, dict):
            for lat_key, lon_key in [("latitude", "longitude"), ("lat", "lon"), ("lat", "lng")]:
                if lat_key in loc and lon_key in loc:
                    return float(loc[lat_key]), float(loc[lon_key])

    raise ValueError(
        f"Não foi possível extrair latitude/longitude do retorno da AeroAPI. Tipo={type(aeroapi_result)}"
    )


def _coletar_dados_rota(origem_id, destino_id, data_futura, corredor_km, limite, internacionais):
    """Reúne sugestão, coordenadas e aeroportos intermediários da rota."""
    sugestao_data = gerar_sugestao_rota(origem_id, destino_id, data_futura)

    lat_o, lon_o = _extract_lat_lon(obter_coordenadas_aeroporto(sugestao_data['origem']))
    lat_d, lon_d = _extract_lat_lon(obter_coordenadas_aeroporto(sugestao_data['destino']))

    intermediarios = aeroportos_no_corredor(
        lat_o, lon_o, lat_d, lon_d,
        corredor_km=corredor_km,
        excluir_iatas=[sugestao_data['origem'], sugestao_data['destino']],
        limite=limite,
        somente_internacionais=internacionais,
    )

    return sugestao_data, (lat_o, lon_o), (lat_d, lon_d), intermediarios


@mapa_bp.route('/mapa_sugerido', methods=['GET'])
def mostrar_mapa_sugerido_animado_html():
    origem_id = request.args.get('origem_id')
    destino_id = request.args.get('destino_id')
    data_futura = request.args.get('data')
    corredor_km = request.args.get('corredor_km', default=_CORREDOR_PADRAO_KM, type=float)
    limite = request.args.get('limite', default=_LIMITE_PADRAO, type=int)
    internacionais = request.args.get('internacionais', default='true', type=str).lower() != 'false'
    formato = request.args.get('formato', default='html', type=str).lower()

    if not origem_id or not destino_id or not data_futura:
        return jsonify({"erro": "Os parâmetros 'origem_id', 'destino_id' e 'data' são obrigatórios."}), 400

    validar_data(data_futura)

    sugestao_data, (lat_o, lon_o), (lat_d, lon_d), intermediarios = _coletar_dados_rota(
        origem_id, destino_id, data_futura, corredor_km, limite, internacionais
    )

    origem = sugestao_data['origem']
    destino = sugestao_data['destino']
    risco_origem = sugestao_data['risco_origem']
    risco_destino = sugestao_data['risco_destino']
    sugestao = sugestao_data['sugestao']
    rotas = sugestao_data['rotas']

    dist_direta = distancia_km(lat_o, lon_o, lat_d, lon_d)

    # Modo JSON: útil para clientes/programas e para testes automatizados.
    if formato == 'json':
        return jsonify({
            **{k: v for k, v in sugestao_data.items() if k != '_id'},
            "distancia_direta_km": round(dist_direta, 1),
            "corredor_km": corredor_km,
            "aeroportos_no_caminho": intermediarios,
            "rotas_alternativas": [
                {
                    "via": apt["iata"],
                    "nome": apt["nome"],
                    "cidade": apt.get("cidade", ""),
                    "pais": apt.get("pais", ""),
                    "escalas": [origem, apt["iata"], destino],
                    "desvio_km": apt["desvio_rota_km"],
                }
                for apt in intermediarios
            ],
        })

    # ---------- Renderização do mapa ----------
    mapa = folium.Map(location=[(lat_o + lat_d) / 2, (lon_o + lon_d) / 2], zoom_start=4)

    # Marcadores origem/destino
    folium.Marker(
        [lat_o, lon_o],
        popup=f"Origem: {origem}<br>Risco: {risco_origem}<br>Sugestão: {sugestao}",
        icon=folium.Icon(color='red' if risco_origem == "Alto" else 'green', icon='plane', prefix='fa')
    ).add_to(mapa)
    folium.Marker(
        [lat_d, lon_d],
        popup=f"Destino: {destino}<br>Risco: {risco_destino}<br>Sugestão: {sugestao}",
        icon=folium.Icon(color='red' if risco_destino == "Alto" else 'green', icon='plane', prefix='fa')
    ).add_to(mapa)

    # Rota direta (geodésica curva)
    grupo_direta = folium.FeatureGroup(name=f"Rota direta ({round(dist_direta)} km)")
    folium.PolyLine(
        pontos_geodesicos(lat_o, lon_o, lat_d, lon_d),
        color="blue", weight=4, opacity=0.9,
        tooltip=f"{origem} ➡️ {destino} — {round(dist_direta)} km (direto)"
    ).add_to(grupo_direta)
    grupo_direta.add_to(mapa)

    # Aeroportos no corredor + rotas alternativas via cada um
    grupo_aeroportos = folium.FeatureGroup(name=f"Aeroportos no caminho ({len(intermediarios)})")
    grupo_alternativas = folium.FeatureGroup(name="Rotas alternativas (com escala)", show=False)
    cores = ["purple", "orange", "darkgreen", "cadetblue", "darkred", "darkpurple"]

    for i, apt in enumerate(intermediarios):
        lat_a, lon_a = apt["lat"], apt["lon"]
        cor = cores[i % len(cores)]

        local = ", ".join(p for p in (apt.get("cidade"), apt.get("pais")) if p)
        folium.Marker(
            [lat_a, lon_a],
            popup=(
                f"<b>{apt['iata']}</b> ({apt.get('icao', '')}) — {apt['nome']}<br>"
                f"{local}<br>"
                f"Escala: {origem} → {apt['iata']} → {destino}<br>"
                f"Desvio: +{apt['desvio_rota_km']} km<br>"
                f"Distância da rota direta: {apt['distancia_da_rota_km']} km"
            ),
            icon=folium.Icon(color=cor, icon='plane-departure', prefix='fa')
        ).add_to(grupo_aeroportos)

        # Rota alternativa origem -> hub -> destino
        pontos_alt = (
            pontos_geodesicos(lat_o, lon_o, lat_a, lon_a, n=48)
            + pontos_geodesicos(lat_a, lon_a, lat_d, lon_d, n=48)
        )
        folium.PolyLine(
            pontos_alt, color=cor, weight=2, opacity=0.6, dash_array="6, 10",
            tooltip=f"Via {apt['iata']}: +{apt['desvio_rota_km']} km"
        ).add_to(grupo_alternativas)

    grupo_aeroportos.add_to(mapa)
    grupo_alternativas.add_to(mapa)

    # Rotas filed da AeroAPI (informação complementar, na origem)
    routes_list = rotas.get("routes", []) if isinstance(rotas, dict) else []
    if routes_list:
        grupo_filed = folium.FeatureGroup(name="Rotas registradas (AeroAPI)", show=False)
        for rota in routes_list:
            popup_content = f"""
                <b>Tipo de Aeronave:</b> {', '.join(rota.get('aircraft_types', []))}<br>
                <b>Altitude:</b> {rota.get('filed_altitude_min', '-')} - {rota.get('filed_altitude_max', '-')} ft<br>
                <b>Distância:</b> {rota.get('route_distance', '-')}<br>
                <b>Última Partida:</b> {rota.get('last_departure_time', '-')}<br>
                <b>Rota:</b> {rota.get('route', '-')}
            """
            folium.Marker(
                [lat_o, lon_o],
                popup=folium.Popup(popup_content, max_width=300),
                icon=folium.Icon(color='lightgray', icon='route', prefix='fa')
            ).add_to(grupo_filed)
        grupo_filed.add_to(mapa)

    folium.LayerControl(collapsed=False).add_to(mapa)

    html = mapa.get_root().render()
    return Response(html, mimetype="text/html")
