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
    
    response = requests.get(API_URL, headers=HEADERS, params=params)
    data = response.json()

    if 'data' in data:
        df = pd.DataFrame(data['data'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df = df.dropna(subset=['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres'])
    else:
        raise ValueError("Erro ao obter dados da API Meteostat.")

    df['risk'] = df.apply(lambda row: 1 if row['tmax'] > 35 or row['prcp'] > 50 or row['wspd'] > 25 else 0, axis=1)
    
    return df
