"""Cálculos geográficos: rota geodésica (great-circle), distâncias e
identificação de aeroportos que ficam no corredor entre dois pontos.

A base de aeroportos (``data/airports.json``) é derivada da OurAirports e
gerada por ``scripts/build_airports.py`` — totalmente offline e determinística,
sem chamadas a APIs externas em runtime.

A seleção de aeroportos no corredor usa haversine vetorizado (numpy) para
filtrar milhares de aeroportos rapidamente, e refina os selecionados com a
distância geodésica precisa (WGS84).
"""
import json
import os
from functools import lru_cache

import numpy as np
from geographiclib.geodesic import Geodesic

_GEOD = Geodesic.WGS84
_EARTH_RADIUS_KM = 6371.0088
_AIRPORTS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "airports.json")


@lru_cache(maxsize=1)
def carregar_aeroportos():
    """Carrega (uma única vez) a base de aeroportos."""
    with open(_AIRPORTS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _arrays_aeroportos():
    """Arrays numpy (lat, lon) alinhados à lista de aeroportos, para vetorização."""
    apts = carregar_aeroportos()
    lats = np.fromiter((a["lat"] for a in apts), dtype=float, count=len(apts))
    lons = np.fromiter((a["lon"] for a in apts), dtype=float, count=len(apts))
    return apts, lats, lons


def distancia_km(lat1, lon1, lat2, lon2):
    """Distância geodésica (great-circle, WGS84) em quilômetros."""
    return _GEOD.Inverse(lat1, lon1, lat2, lon2)["s12"] / 1000.0


def pontos_geodesicos(lat1, lon1, lat2, lon2, n=64):
    """Retorna ``n+1`` pontos [lat, lon] ao longo da geodésica entre os pontos."""
    n = max(1, int(n))
    line = _GEOD.InverseLine(lat1, lon1, lat2, lon2)
    total = line.s13
    pontos = []
    for i in range(n + 1):
        s = total * i / n
        pos = line.Position(s, Geodesic.STANDARD | Geodesic.LONG_UNROLL)
        pontos.append([pos["lat2"], pos["lon2"]])
    return pontos


def _haversine_matriz_km(lat_pts, lon_pts, lat_apts, lon_apts):
    """Distância haversine entre S pontos e A aeroportos -> matriz (A x S) em km."""
    phi_p = np.radians(lat_pts)[None, :]      # 1 x S
    lam_p = np.radians(lon_pts)[None, :]      # 1 x S
    phi_a = np.radians(lat_apts)[:, None]     # A x 1
    lam_a = np.radians(lon_apts)[:, None]     # A x 1

    dphi = phi_p - phi_a
    dlam = lam_p - lam_a
    a = np.sin(dphi / 2.0) ** 2 + np.cos(phi_a) * np.cos(phi_p) * np.sin(dlam / 2.0) ** 2
    return 2.0 * _EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def _eh_internacional(nome):
    n = (nome or "").lower()
    return "international" in n or "intl" in n


def aeroportos_no_corredor(lat1, lon1, lat2, lon2, corredor_km=400.0,
                           excluir_iatas=None, n_amostras=120, limite=None,
                           somente_internacionais=True):
    """Identifica aeroportos da base que ficam dentro de um corredor ao longo
    da rota entre (lat1, lon1) e (lat2, lon2).

    Um aeroporto entra no resultado quando sua menor distância à geodésica é
    <= ``corredor_km`` e o ponto mais próximo não está nas extremidades da rota
    (evita capturar os próprios aeroportos de origem/destino ou pontos além
    deles). Cada item traz ``desvio_rota_km`` = distância extra de uma escala
    origem -> aeroporto -> destino em relação à rota direta.

    ``somente_internacionais`` (padrão) mantém apenas aeroportos com
    "International"/"Intl" no nome — um proxy honesto de relevância como hub,
    já que a base OurAirports empacotada não traz o porte do aeroporto. Passe
    False para incluir todos os aeroportos com código IATA no corredor.

    Retorna a lista ordenada por menor desvio; ``limite`` corta o número de
    resultados (None = todos).
    """
    excluir = {i.upper() for i in (excluir_iatas or [])}
    apts, lats, lons = _arrays_aeroportos()

    amostras = pontos_geodesicos(lat1, lon1, lat2, lon2, n=n_amostras)

    # Ignora amostras muito próximas às extremidades (5% de cada ponta).
    margem = max(1, int(len(amostras) * 0.05))
    miolo = amostras[margem:len(amostras) - margem] or amostras
    sample_lats = np.fromiter((p[0] for p in miolo), dtype=float, count=len(miolo))
    sample_lons = np.fromiter((p[1] for p in miolo), dtype=float, count=len(miolo))

    # Menor distância de cada aeroporto à rota (haversine vetorizado, rápido).
    menor_dist = _haversine_matriz_km(sample_lats, sample_lons, lats, lons).min(axis=1)
    candidatos_idx = np.nonzero(menor_dist <= corredor_km)[0]

    dist_direta = distancia_km(lat1, lon1, lat2, lon2)

    resultado = []
    for idx in candidatos_idx:
        apt = apts[idx]
        if apt["iata"].upper() in excluir:
            continue
        if somente_internacionais and not _eh_internacional(apt["nome"]):
            continue

        # Refina o desvio com a distância geodésica precisa (poucos aeroportos).
        desvio = (
            distancia_km(lat1, lon1, apt["lat"], apt["lon"])
            + distancia_km(apt["lat"], apt["lon"], lat2, lon2)
            - dist_direta
        )
        resultado.append({
            **apt,
            "desvio_rota_km": round(desvio, 1),
            "distancia_da_rota_km": round(float(menor_dist[idx]), 1),
        })

    resultado.sort(key=lambda a: a["desvio_rota_km"])
    if limite is not None:
        resultado = resultado[:int(limite)]
    return resultado
