import requests
import pandas as pd
from config import API_URL, HEADERS

def carregar_dados(lat, lon):
    params = {
        "lat": lat,
        "lon": lon,
        "start": "2018-01-01",
        "end": "2024-11-01",
        "units": "metric"
    }
    
    response = requests.get(API_URL, headers=HEADERS, params=params, timeout=10)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        body_summary = response.text.strip().replace("\n", " ")[:200] or "<sem corpo>"
        raise ValueError(
            f"Erro na API Meteostat (status {response.status_code}): {body_summary}"
        ) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise ValueError("Erro ao interpretar resposta JSON da API Meteostat.") from exc

    if 'data' in data:
        df = pd.DataFrame(data['data'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df = df.dropna(subset=['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres'])
    else:
        body_summary = response.text.strip().replace("\n", " ")[:200] or "<sem corpo>"
        raise ValueError(
            f"Erro ao obter dados da API Meteostat (status {response.status_code}): {body_summary}"
        )

    df['risk'] = df.apply(lambda row: 1 if row['tmax'] > 35 or row['prcp'] > 50 or row['wspd'] > 25 else 0, axis=1)
    
    return df
