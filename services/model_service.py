from datetime import datetime, timedelta
import os

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from prophet import Prophet
from requests import HTTPError

CACHE_TTL_HOURS = int(os.getenv("MODEL_CACHE_TTL_HOURS", "24"))
CACHE_TTL = timedelta(hours=CACHE_TTL_HOURS)
_MODEL_CACHE = {}

FEATURES = ['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']
MIN_PROPHET_POINTS = int(os.getenv("MIN_PROPHET_POINTS", "60"))
PROPHET_INTERVAL_WIDTH = float(os.getenv("PROPHET_INTERVAL_WIDTH", "0.8"))

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

def _prepare_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError("DataFrame vazio: não há dados para treinar o modelo.")

    missing = [c for c in FEATURES + ["risk"] if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame sem colunas necessárias: {missing}")

    frame = df.copy()

    for c in FEATURES + ["risk"]:
        frame[c] = pd.to_numeric(frame[c], errors="coerce")

    frame = frame.dropna(subset=["risk", "tavg", "tmin", "tmax", "prcp"])

    frame["wspd"] = frame["wspd"].fillna(0)
    if frame["pres"].isna().all():
        frame["pres"] = 1013.25
    else:
        frame["pres"] = frame["pres"].fillna(frame["pres"].median())

    if frame.empty:
        raise ValueError("Após limpeza, o DataFrame ficou vazio (sem amostras válidas).")

    return frame

def treinar_modelo(df, lat, lon):
    entry = _get_cache_entry(lat, lon)
    if _is_cache_valid(entry) and entry["rf_model"] is not None:
        return entry["rf_model"]

    entry = _reset_cache_entry(lat, lon)

    frame = _prepare_training_frame(df)
    X = frame[FEATURES]
    y = frame["risk"].astype(int)

    model = RandomForestClassifier(
        n_estimators=200,
        random_state=42,
        min_samples_leaf=2,
        max_features="sqrt",
        n_jobs=-1,
    )
    model.fit(X, y)
    entry["rf_model"] = model
    return model

def prever_variavel(df, coluna, data_futura, lat, lon):
    if coluna not in FEATURES:
        raise ValueError(f"Coluna inválida para previsão: {coluna}")

    entry = _get_cache_entry(lat, lon)
    if not _is_cache_valid(entry):
        entry = _reset_cache_entry(lat, lon)

    modelo = entry["prophet_models"].get(coluna)
    if modelo is None:
        if df is None or df.empty:
            raise ValueError("DataFrame vazio: não há dados para treinar o Prophet.")
        if coluna not in df.columns:
            raise ValueError(f"DataFrame não possui a coluna '{coluna}'.")

        prophet_df = df[[coluna]].reset_index()
        prophet_df.columns = ["ds", "y"]
        prophet_df["ds"] = pd.to_datetime(prophet_df["ds"], errors="coerce")
        prophet_df["y"] = pd.to_numeric(prophet_df["y"], errors="coerce")
        prophet_df = prophet_df.dropna(subset=["ds", "y"]).sort_values("ds")

        if len(prophet_df) < MIN_PROPHET_POINTS:
            return float(prophet_df["y"].median()) if len(prophet_df) > 0 else 0.0

        modelo = Prophet(interval_width=PROPHET_INTERVAL_WIDTH)
        modelo.fit(prophet_df)
        entry["prophet_models"][coluna] = modelo

    futuro = pd.DataFrame({"ds": [pd.to_datetime(data_futura)]})
    previsao = modelo.predict(futuro)
    yhat = float(previsao["yhat"].values[0])

    if coluna in ("prcp", "wspd"):
        yhat = max(0.0, yhat)

    return yhat