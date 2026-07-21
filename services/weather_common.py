"""Lógica compartilhada entre provedores de dados meteorológicos.

Qualquer provider (Meteostat, Open-Meteo, ...) deve produzir um DataFrame
indexado por data com as colunas em ``BASE_FEATURES`` e delegar a
``finalizar_clima`` a limpeza final e o cálculo do risco — garantindo que o
rótulo de risco seja idêntico independentemente da fonte.
"""
import pandas as pd

from config import BASE_FEATURES

FEATURES = BASE_FEATURES

# Pressão neutra ao nível do mar (hPa), usada como fallback.
_PRES_FALLBACK = 1013.25


def _risk_score_daily(row) -> int:
    """Score de risco diário a partir de calor, chuva e vento."""
    score = 0
    tmax = row["tmax"]
    prcp = row["prcp"]
    wspd = row["wspd"]

    # calor (dia, °C)
    if tmax >= 38:
        score += 3
    elif tmax >= 35:
        score += 2
    elif tmax >= 32:
        score += 1

    # chuva (dia, mm)
    if prcp >= 80:
        score += 3
    elif prcp >= 50:
        score += 2
    elif prcp >= 30:
        score += 1

    # vento (dia, km/h)
    if wspd >= 60:
        score += 3
    elif wspd >= 45:
        score += 2
    elif wspd >= 35:
        score += 1

    return score


def finalizar_clima(df: pd.DataFrame, fonte: str = "provedor") -> pd.DataFrame:
    """Normaliza colunas, preenche buracos e calcula risco_score/risk.

    ``df`` deve estar indexado por data e conter (idealmente) as colunas de
    ``FEATURES``. Colunas ausentes são criadas como NaN e tratadas.
    """
    df = df.sort_index()

    # garante colunas e tipos numéricos
    for col in FEATURES:
        if col not in df.columns:
            df[col] = pd.NA
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # preenchimentos seguros (dados diários às vezes têm buracos)
    df[FEATURES] = df[FEATURES].ffill().bfill()

    # wspd frequentemente nulo → não pode derrubar tudo
    df["wspd"] = df["wspd"].fillna(0)

    # pres: se vier tudo nulo, usa fallback neutro
    if df["pres"].isna().all():
        df["pres"] = _PRES_FALLBACK
    else:
        df["pres"] = df["pres"].fillna(df["pres"].median())

    # mantém só o essencial pra risco/treino
    df = df.dropna(subset=["tavg", "tmin", "tmax", "prcp"])
    if df.empty:
        raise ValueError(
            f"A fonte {fonte} retornou dados, mas após limpeza o DataFrame ficou vazio."
        )

    df["risk_score"] = df.apply(_risk_score_daily, axis=1)
    df["risk"] = (df["risk_score"] >= 3).astype(int)

    return df
