from datetime import date

from services.http_client import session
import pandas as pd
from config import API_URL, HEADERS, BASE_FEATURES, HISTORICAL_START_DATE
from requests import HTTPError

FEATURES = BASE_FEATURES

def carregar_dados(lat, lon):
    params = {
        "lat": lat,
        "lon": lon,
        "start": HISTORICAL_START_DATE,
        # Data final dinâmica: hoje (dados históricos disponíveis até o presente).
        "end": date.today().isoformat(),
        "units": "metric",
    }

    response = session.get(API_URL, headers=HEADERS, params=params, timeout=15)
    try:
        response.raise_for_status()
    except HTTPError as exc:
        body_summary = response.text.strip().replace("\n", " ")[:200] or "<sem corpo>"
        raise ValueError(f"Erro na API Meteostat (status {response.status_code}): {body_summary}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError("Erro ao interpretar resposta JSON da API Meteostat.") from exc

    data = payload.get("data")
    if not data:
        raise ValueError("A API Meteostat retornou 'data' vazio para os parâmetros informados.")

    df = pd.DataFrame(data)

    if "date" not in df.columns:
        raise ValueError(f"Resposta Meteostat sem campo 'date'. Colunas: {list(df.columns)}")

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
        raise ValueError("Meteostat retornou dados, mas após limpeza o DataFrame ficou vazio.")

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
