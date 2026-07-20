"""Cálculos geográficos: rota geodésica (great-circle), distâncias e
identificação de aeroportos que ficam no corredor entre dois pontos.

Usa a base curada em ``data/airports.json`` — totalmente offline e
determinística, sem chamadas adicionais a APIs externas.
"""
import json
import os
from functools import lru_cache

from geographiclib.geodesic import Geodesic

_GEOD = Geodesic.WGS84
_AIRPORTS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "airports.json")


@lru_cache(maxsize=1)
def carregar_aeroportos():
    """Carrega (uma única vez) a base de aeroportos principais."""
    with open(_AIRPORTS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def distancia_km(lat1, lon1, lat2, lon2):
    """Distância geodésica (great-circle) em quilômetros."""
    return _GEOD.Inverse(lat1, lon1, lat2, lon2)["s12"] / 1000.0


def pontos_geodesicos(lat1, lon1, lat2, lon2, n=64):
    """Retorna ``n+1`` pontos [lat, lon] ao longo da geodésica entre os pontos.

    Serve para desenhar a rota como uma curva realista no mapa em vez de
    uma linha reta na projeção plana.
    """
    n = max(1, int(n))
    line = _GEOD.InverseLine(lat1, lon1, lat2, lon2)
    total = line.s13
    pontos = []
    for i in range(n + 1):
        s = total * i / n
        pos = line.Position(s, Geodesic.STANDARD | Geodesic.LONG_UNROLL)
        pontos.append([pos["lat2"], pos["lon2"]])
    return pontos


def aeroportos_no_corredor(lat1, lon1, lat2, lon2, corredor_km=400.0,
                           excluir_iatas=None, n_amostras=120):
    """Identifica aeroportos da base que ficam dentro de um corredor ao longo
    da rota entre (lat1, lon1) e (lat2, lon2).

    Um aeroporto entra no resultado quando sua menor distância à geodésica é
    <= ``corredor_km`` e o ponto mais próximo não está nas extremidades da rota
    (para não capturar os próprios aeroportos de origem/destino ou pontos além
    deles). Cada item traz ``desvio_km`` = distância extra de uma escala
    origem -> aeroporto -> destino em relação à rota direta.

    Retorna a lista ordenada por menor desvio.
    """
    excluir = {i.upper() for i in (excluir_iatas or [])}
    amostras = pontos_geodesicos(lat1, lon1, lat2, lon2, n=n_amostras)
    dist_direta = distancia_km(lat1, lon1, lat2, lon2)

    # Ignora amostras muito próximas às extremidades (5% de cada ponta).
    margem = max(1, int(len(amostras) * 0.05))
    miolo = amostras[margem:len(amostras) - margem]
    if not miolo:
        miolo = amostras

    resultado = []
    for apt in carregar_aeroportos():
        if apt["iata"].upper() in excluir:
            continue

        menor = min(distancia_km(apt["lat"], apt["lon"], p[0], p[1]) for p in miolo)
        if menor > corredor_km:
            continue

        desvio = (
            distancia_km(lat1, lon1, apt["lat"], apt["lon"])
            + distancia_km(apt["lat"], apt["lon"], lat2, lon2)
            - dist_direta
        )
        resultado.append({
            **apt,
            "desvio_rota_km": round(desvio, 1),
            "distancia_da_rota_km": round(menor, 1),
        })

    resultado.sort(key=lambda a: a["desvio_rota_km"])
    return resultado
