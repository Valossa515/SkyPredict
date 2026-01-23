from datetime import datetime, timedelta
import os

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from prophet import Prophet

CACHE_TTL_HOURS = int(os.getenv("MODEL_CACHE_TTL_HOURS", "24"))
CACHE_TTL = timedelta(hours=CACHE_TTL_HOURS)
_MODEL_CACHE = {}


def _cache_key(lat, lon):
    return (float(lat), float(lon))


def _is_cache_valid(entry):
    return entry and datetime.utcnow() - entry["updated_at"] < CACHE_TTL


def _get_cache_entry(lat, lon):
    return _MODEL_CACHE.get(_cache_key(lat, lon))


def _reset_cache_entry(lat, lon):
    entry = {"updated_at": datetime.utcnow(), "rf_model": None, "prophet_models": {}}
    _MODEL_CACHE[_cache_key(lat, lon)] = entry
    return entry


def clear_model_cache(lat=None, lon=None):
    if lat is None or lon is None:
        _MODEL_CACHE.clear()
        return
    _MODEL_CACHE.pop(_cache_key(lat, lon), None)

def treinar_modelo(df, lat, lon):
    entry = _get_cache_entry(lat, lon)
    if _is_cache_valid(entry) and entry["rf_model"] is not None:
        return entry["rf_model"]

    entry = _reset_cache_entry(lat, lon)
    X = df[['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']]
    y = df['risk']
    model = RandomForestClassifier(n_estimators=100, random_state=42, min_samples_leaf=1, max_features='sqrt')
    model.fit(X, y)
    entry["rf_model"] = model
    return model

def prever_variavel(df, coluna, data_futura, lat, lon):
    entry = _get_cache_entry(lat, lon)
    if not _is_cache_valid(entry):
        entry = _reset_cache_entry(lat, lon)

    modelo = entry["prophet_models"].get(coluna)
    if modelo is None:
        prophet_df = df[[coluna]].reset_index()
        prophet_df.columns = ['ds', 'y']
        modelo = Prophet()
        modelo.fit(prophet_df)
        entry["prophet_models"][coluna] = modelo

    futuro = pd.DataFrame({'ds': [data_futura]})
    previsao = modelo.predict(futuro)
    return previsao['yhat'].values[0]
