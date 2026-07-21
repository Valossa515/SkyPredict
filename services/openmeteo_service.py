"""Provedor de dados meteorológicos Open-Meteo (fallback sem API key).

A Open-Meteo (https://open-meteo.com/) oferece histórico diário gratuito
(reanálise ERA5) sem necessidade de chave de API. Produz o mesmo DataFrame
padronizado dos demais provedores via ``finalizar_clima``.

Observação: a agregação diária da Open-Meteo não inclui pressão atmosférica,
então a coluna ``pres`` fica com o fallback neutro (1013.25 hPa) — o modelo
tolera isso (a mesma lógica já existe para o Meteostat quando falta pressão).
"""
import os
from datetime import date

import pandas as pd

from services.http_client import session
from services.weather_common import finalizar_clima
from config import HISTORICAL_START_DATE

ARCHIVE_URL = os.getenv("OPENMETEO_ARCHIVE_URL", "https://archive-api.open-meteo.com/v1/archive")

# Mapeamento variável Open-Meteo -> coluna do projeto.
_DAILY_MAP = {
    "temperature_2m_mean": "tavg",
    "temperature_2m_min": "tmin",
    "temperature_2m_max": "tmax",
    "precipitation_sum": "prcp",
    "windspeed_10m_max": "wspd",
}


def carregar_dados(lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": HISTORICAL_START_DATE,
        "end_date": date.today().isoformat(),
        "daily": ",".join(_DAILY_MAP.keys()),
        "timezone": "UTC",
        # unidades explícitas para casar com os limiares de risco (km/h, °C, mm)
        "windspeed_unit": "kmh",
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
    }

    response = session.get(ARCHIVE_URL, params=params, timeout=30)
    if not response.ok:
        body = response.text.strip().replace("\n", " ")[:200] or "<sem corpo>"
        raise ValueError(f"Erro na API Open-Meteo (status {response.status_code}): {body}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError("Erro ao interpretar resposta JSON da API Open-Meteo.") from exc

    daily = payload.get("daily")
    if not daily or not daily.get("time"):
        raise ValueError("A API Open-Meteo retornou 'daily' vazio para os parâmetros informados.")

    df = pd.DataFrame({"date": pd.to_datetime(daily["time"], errors="coerce")})
    for origem, destino in _DAILY_MAP.items():
        df[destino] = daily.get(origem)

    df = df.dropna(subset=["date"]).set_index("date")

    return finalizar_clima(df, fonte="Open-Meteo")
