from datetime import date

from services.http_client import session
from services.weather_common import finalizar_clima, FEATURES
import pandas as pd
from config import API_URL, HEADERS, HISTORICAL_START_DATE
from requests import HTTPError

__all__ = ["carregar_dados", "FEATURES"]


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
    df = df.dropna(subset=["date"]).set_index("date")

    return finalizar_clima(df, fonte="Meteostat")
