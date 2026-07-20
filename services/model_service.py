from datetime import datetime, timedelta, timezone
import os
import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.dummy import DummyClassifier
from prophet import Prophet

from config import BASE_FEATURES

logger = logging.getLogger(__name__)

CACHE_TTL_HOURS = int(os.getenv("MODEL_CACHE_TTL_HOURS", "24"))
CACHE_TTL = timedelta(hours=CACHE_TTL_HOURS)
_MODEL_CACHE = {}
# Features derivadas para engenharia de features
DERIVED_FEATURES = ['temp_amplitude', 'temp_ratio', 'heat_index', 'wind_chill',
                    'month', 'season', 'prcp_wspd_interaction', 'extreme_temp_flag']
# Todas as features para o modelo
FEATURES = BASE_FEATURES  # Mantém compatibilidade com código existente
ENHANCED_FEATURES = BASE_FEATURES + DERIVED_FEATURES

MIN_PROPHET_POINTS = int(os.getenv("MIN_PROPHET_POINTS", "60"))
PROPHET_INTERVAL_WIDTH = float(os.getenv("PROPHET_INTERVAL_WIDTH", "0.8"))

# Configuração para otimização de hiperparâmetros
ENABLE_HYPERPARAMETER_TUNING = os.getenv("ENABLE_HYPERPARAMETER_TUNING", "false").lower() == "true"

def _cache_key(lat, lon):
    return (float(lat), float(lon))

def _is_cache_valid(entry):
    return entry and datetime.now(timezone.utc) - entry["updated_at"] < CACHE_TTL

def _get_cache_entry(lat, lon):
    return _MODEL_CACHE.get(_cache_key(lat, lon))

def _reset_cache_entry(lat, lon):
    entry = {"updated_at": datetime.now(timezone.utc), "rf_model": None, "prophet_models": {}, "scaler": None}
    _MODEL_CACHE[_cache_key(lat, lon)] = entry
    return entry


def _create_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cria features derivadas para melhorar a capacidade preditiva do modelo.
    """
    frame = df.copy()

    # Amplitude térmica (diferença entre máxima e mínima)
    frame['temp_amplitude'] = frame['tmax'] - frame['tmin']

    # Razão temperatura média / máxima
    frame['temp_ratio'] = frame['tavg'] / frame['tmax'].replace(0, 1)

    # Índice de calor simplificado (Heat Index aproximado)
    # Fórmula simplificada: quando temp > 27°C
    frame['heat_index'] = np.where(
        frame['tavg'] > 27,
        frame['tavg'] + 0.33 * frame['pres'] / 100 - 4.0,
        frame['tavg']
    )

    # Wind chill (sensação térmica com vento) - fórmula simplificada
    # Aplicável quando temp < 10°C e vento > 4.8 km/h
    frame['wind_chill'] = np.where(
        (frame['tavg'] < 10) & (frame['wspd'] > 4.8),
        13.12 + 0.6215 * frame['tavg'] - 11.37 * (frame['wspd'] ** 0.16) + 0.3965 * frame['tavg'] * (frame['wspd'] ** 0.16),
        frame['tavg']
    )

    # Features temporais (se houver índice de data)
    if isinstance(frame.index, pd.DatetimeIndex):
        frame['month'] = frame.index.month.values
        frame['season'] = pd.Series(frame.index.month).map(lambda m: (m % 12 + 3) // 3).values  # 1=verão, 2=outono, 3=inverno, 4=primavera (hemisfério sul)
    else:
        frame['month'] = 6  # valor default
        frame['season'] = 2  # valor default

    # Interação precipitação x vento (condições adversas combinadas)
    frame['prcp_wspd_interaction'] = frame['prcp'] * frame['wspd'] / 100

    # Flag de temperatura extrema
    frame['extreme_temp_flag'] = ((frame['tmax'] >= 35) | (frame['tmin'] <= 5)).astype(int)

    return frame

def clear_model_cache(lat=None, lon=None):
    if lat is None or lon is None:
        _MODEL_CACHE.clear()
        return
    _MODEL_CACHE.pop(_cache_key(lat, lon), None)

def _prepare_training_frame(df: pd.DataFrame, use_enhanced_features: bool = True) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError("DataFrame vazio: não há dados para treinar o modelo.")

    missing = [c for c in BASE_FEATURES + ["risk"] if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame sem colunas necessárias: {missing}")

    frame = df.copy()

    for c in BASE_FEATURES + ["risk"]:
        frame[c] = pd.to_numeric(frame[c], errors="coerce")

    frame = frame.dropna(subset=["risk", "tavg", "tmin", "tmax", "prcp"])

    frame["wspd"] = frame["wspd"].fillna(0)
    if frame["pres"].isna().all():
        frame["pres"] = 1013.25
    else:
        frame["pres"] = frame["pres"].fillna(frame["pres"].median())

    if frame.empty:
        raise ValueError("Após limpeza, o DataFrame ficou vazio (sem amostras válidas).")

    # Criar features derivadas se solicitado
    if use_enhanced_features:
        frame = _create_derived_features(frame)
        # Preencher valores NaN nas features derivadas
        for col in DERIVED_FEATURES:
            if col in frame.columns:
                frame[col] = frame[col].fillna(frame[col].median() if frame[col].notna().any() else 0)

    return frame

def treinar_modelo(df, lat, lon, use_enhanced_features: bool = True):
    """
    Treina um modelo de classificação de risco meteorológico com melhorias:
    - Engenharia de features avançada
    - Ensemble de modelos (Random Forest + Gradient Boosting)
    - Tratamento de desbalanceamento de classes
    - Normalização de dados
    - Otimização de hiperparâmetros (opcional via env var)
    - Tratamento de classe única (DummyClassifier)
    """
    entry = _get_cache_entry(lat, lon)
    if _is_cache_valid(entry) and entry["rf_model"] is not None:
        return entry["rf_model"]

    entry = _reset_cache_entry(lat, lon)

    frame = _prepare_training_frame(df, use_enhanced_features=use_enhanced_features)

    # Selecionar features baseado na configuração
    feature_cols = ENHANCED_FEATURES if use_enhanced_features else BASE_FEATURES
    # Filtrar apenas as features que existem no dataframe
    feature_cols = [f for f in feature_cols if f in frame.columns]

    X = frame[feature_cols]
    y = frame["risk"].astype(int)

    # Verificar número de classes
    class_counts = y.value_counts()
    n_classes = len(class_counts)

    # Normalização dos dados
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    entry["scaler"] = scaler
    entry["feature_cols"] = feature_cols

    # Se há apenas uma classe, usar DummyClassifier
    if n_classes < 2:
        logger.warning(
            f"Dados para lat={lat}, lon={lon} contêm apenas a classe {class_counts.index[0]}. "
            "Usando DummyClassifier para previsões."
        )
        model = DummyClassifier(strategy='constant', constant=int(class_counts.index[0]))
        model.fit(X_scaled, y)
        entry["rf_model"] = model
        entry["single_class"] = True
        return model

    entry["single_class"] = False
    is_imbalanced = (class_counts.min() / class_counts.max()) < 0.3

    if ENABLE_HYPERPARAMETER_TUNING and len(y) >= 50:
        # Otimização de hiperparâmetros com GridSearchCV
        model = _train_with_hyperparameter_tuning(X_scaled, y, is_imbalanced)
    else:
        # Modelo padrão otimizado
        model = _train_default_model(X_scaled, y, is_imbalanced)

    entry["rf_model"] = model
    return model


def build_ensemble(is_imbalanced: bool) -> VotingClassifier:
    """Cria o ensemble (Random Forest + Gradient Boosting) com soft voting.

    Fonte única de verdade da arquitetura do modelo, reutilizada tanto no
    treino em produção quanto na rota de análise/métricas.
    """
    class_weight = 'balanced' if is_imbalanced else None

    rf = RandomForestClassifier(
        n_estimators=300,
        max_depth=15,
        min_samples_split=5,
        min_samples_leaf=2,
        max_features='sqrt',
        class_weight=class_weight,
        random_state=42,
        n_jobs=-1,
    )

    gb = GradientBoostingClassifier(
        n_estimators=150,
        max_depth=5,
        learning_rate=0.1,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
    )

    return VotingClassifier(
        estimators=[('rf', rf), ('gb', gb)],
        voting='soft',
        n_jobs=-1,
    )


def build_ensemble_pipeline(is_imbalanced: bool) -> Pipeline:
    """Pipeline (StandardScaler -> ensemble).

    Usar o pipeline em validação cruzada garante que a normalização seja
    ajustada apenas no fold de treino, evitando data leakage nas métricas.
    """
    return Pipeline([
        ('scaler', StandardScaler()),
        ('ensemble', build_ensemble(is_imbalanced)),
    ])


def _train_default_model(X, y, is_imbalanced: bool):
    """
    Treina um modelo padrão otimizado usando Voting Classifier (ensemble).
    """
    ensemble = build_ensemble(is_imbalanced)
    ensemble.fit(X, y)
    return ensemble


def _train_with_hyperparameter_tuning(X, y, is_imbalanced: bool):
    """
    Treina modelo com otimização de hiperparâmetros via GridSearchCV.
    """
    class_weight = 'balanced' if is_imbalanced else None

    # Definir grid de parâmetros
    param_grid = {
        'n_estimators': [100, 200, 300],
        'max_depth': [10, 15, 20, None],
        'min_samples_split': [2, 5, 10],
        'min_samples_leaf': [1, 2, 4],
        'max_features': ['sqrt', 'log2'],
    }

    rf = RandomForestClassifier(
        class_weight=class_weight,
        random_state=42,
        n_jobs=-1
    )

    # Validação cruzada estratificada
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    grid_search = GridSearchCV(
        estimator=rf,
        param_grid=param_grid,
        cv=cv,
        scoring='f1_weighted',  # F1-score ponderado para classes desbalanceadas
        n_jobs=-1,
        verbose=0
    )

    grid_search.fit(X, y)
    return grid_search.best_estimator_


def prever_com_modelo(df, model, lat, lon, data_futura: str = None, use_enhanced_features: bool = True):
    """
    Faz previsão usando o modelo treinado, aplicando as mesmas transformações.
    """
    entry = _get_cache_entry(lat, lon)
    scaler = entry.get("scaler") if entry else None
    feature_cols = entry.get("feature_cols", BASE_FEATURES) if entry else BASE_FEATURES

    # Preparar dados para previsão
    if isinstance(df, dict):
        pred_df = pd.DataFrame([df])
    else:
        pred_df = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame(df)

    # Adicionar features derivadas se necessário
    if use_enhanced_features and any(f in DERIVED_FEATURES for f in feature_cols):
        # Criar dataframe temporário com índice de data se disponível
        if data_futura:
            pred_df.index = pd.DatetimeIndex([pd.to_datetime(data_futura)])
        pred_df = _create_derived_features(pred_df)

    # Garantir que todas as features necessárias existem
    for col in feature_cols:
        if col not in pred_df.columns:
            pred_df[col] = 0

    X = pred_df[feature_cols]

    # Aplicar normalização se disponível
    if scaler is not None:
        X_scaled = scaler.transform(X)
    else:
        X_scaled = X.values

    return model.predict(X_scaled)

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