import logging
from datetime import date, datetime

import pandas as pd
from meteostat import Daily, Point

from services.http_client import session
from config import BASE_FEATURES, HISTORICAL_START_DATE, OPEN_METEO_URL

FEATURES = BASE_FEATURES

logger = logging.getLogger(__name__)


def _linhas_via_pacote_meteostat(lat, lon):
    inicio = datetime.strptime(HISTORICAL_START_DATE, "%Y-%m-%d")
    fim = datetime.combine(date.today(), datetime.min.time())

    df = Daily(Point(lat, lon), inicio, fim).fetch()
    if df.empty:
        raise ValueError("Pacote meteostat não retornou dados para as coordenadas informadas.")

    return df.reset_index().rename(columns={"time": "date"})


def _linhas_via_open_meteo(lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": HISTORICAL_START_DATE,
        "end_date": date.today().isoformat(),
        "daily": "temperature_2m_mean,temperature_2m_min,temperature_2m_max,precipitation_sum,wind_speed_10m_max,surface_pressure_mean",
        "timezone": "UTC",
    }
    response = session.get(OPEN_METEO_URL, params=params, timeout=30)
    response.raise_for_status()

    payload = response.json()
    diario = payload.get("daily") or {}
    if not diario.get("time"):
        raise ValueError("A API Open-Meteo retornou dados vazios para os parâmetros informados.")

    return pd.DataFrame({
        "date": diario["time"],
        "tavg": diario.get("temperature_2m_mean"),
        "tmin": diario.get("temperature_2m_min"),
        "tmax": diario.get("temperature_2m_max"),
        "prcp": diario.get("precipitation_sum"),
        "wspd": diario.get("wind_speed_10m_max"),
        "pres": diario.get("surface_pressure_mean"),
    })


def carregar_dados(lat, lon):
    try:
        df = _linhas_via_pacote_meteostat(lat, lon)
    except Exception as exc:
        logger.warning("Falha ao obter dados via pacote meteostat (%s); usando fallback Open-Meteo.", exc)
        df = _linhas_via_open_meteo(lat, lon)

    if "date" not in df.columns:
        raise ValueError(f"Resposta sem campo 'date'. Colunas: {list(df.columns)}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date").sort_index()

    # garante colunas e tipos
    for col in FEATURES:
        if col not in df.columns:
            df[col] = pd.NA
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # preenchimentos seguros (daily às vezes tem buracos)
    df[FEATURES] = df[FEATURES].ffill().bfill()

    # wspd frequentemente nulo → não pode derrubar tudo
    df["wspd"] = df["wspd"].fillna(0)

    # pres: se vier tudo nulo, usa fallback neutro
    if df["pres"].isna().all():
        df["pres"] = 1013.25
    else:
        df["pres"] = df["pres"].fillna(df["pres"].median())

    # mantenha só o essencial pra risco/treino
    df = df.dropna(subset=["tavg", "tmin", "tmax", "prcp"])
    if df.empty:
        raise ValueError("Dados meteorológicos retornados, mas após limpeza o DataFrame ficou vazio.")

    # ---------- RISCO DAILY ----------
    # prcp aqui é mm/dia, wspd geralmente km/h
    def _risk_score_daily(row) -> int:
        score = 0

        tmax = row["tmax"]
        prcp = row["prcp"]
        wspd = row["wspd"]

        # calor (dia)
        if tmax >= 38: score += 3
        elif tmax >= 35: score += 2
        elif tmax >= 32: score += 1

        # chuva (dia, mm)
        if prcp >= 80: score += 3
        elif prcp >= 50: score += 2
        elif prcp >= 30: score += 1

        # vento (dia, km/h)
        if wspd >= 60: score += 3
        elif wspd >= 45: score += 2
        elif wspd >= 35: score += 1

        return score

    df["risk_score"] = df.apply(_risk_score_daily, axis=1)
    df["risk"] = (df["risk_score"] >= 3).astype(int)

    return df
