from flask import Blueprint, request, jsonify, send_file
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import io
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                            f1_score, precision_score, recall_score, roc_auc_score)
from services.meteostat_service import carregar_dados
from services.model_service import (BASE_FEATURES, ENHANCED_FEATURES, _prepare_training_frame,
                                    build_ensemble_pipeline)
from services.validators import validar_coordenadas

analise_bp = Blueprint('analise', __name__)

# Coordenadas default (São Paulo) usadas quando não informadas.
_DEFAULT_LAT = -23.5505
_DEFAULT_LON = -46.6333


def _convert_numpy_types(obj):
    """
    Converte recursivamente tipos numpy para tipos Python nativos
    para garantir serialização JSON correta.
    """
    if isinstance(obj, dict):
        return {_convert_numpy_types(k): _convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_numpy_types(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def _preparar_dataset(lat, lon, use_enhanced):
    """Carrega dados, prepara o frame e devolve (X, y, feature_cols, is_imbalanced)."""
    df = carregar_dados(lat, lon)
    frame = _prepare_training_frame(df, use_enhanced_features=use_enhanced)

    feature_cols = ENHANCED_FEATURES if use_enhanced else BASE_FEATURES
    feature_cols = [f for f in feature_cols if f in frame.columns]

    X = frame[feature_cols]
    y = frame['risk']

    class_counts = y.value_counts()
    is_imbalanced = len(class_counts) > 1 and (class_counts.min() / class_counts.max()) < 0.3

    return X, y, feature_cols, is_imbalanced, class_counts


@analise_bp.route('/analise', methods=['GET'])
def analise():
    lat, lon = validar_coordenadas(
        request.args.get('lat', default=_DEFAULT_LAT),
        request.args.get('lon', default=_DEFAULT_LON),
    )
    use_enhanced = request.args.get('enhanced', default='true', type=str).lower() == 'true'

    X, y, feature_cols, is_imbalanced, class_counts = _preparar_dataset(lat, lon, use_enhanced)

    # Split estratificado
    x_train, x_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Pipeline (scaler + ensemble): a normalização é ajustada só no treino.
    model = build_ensemble_pipeline(is_imbalanced)
    model.fit(x_train, y_train)

    y_pred = model.predict(x_test)
    y_pred_proba = model.predict_proba(x_test)[:, 1] if hasattr(model, 'predict_proba') else None

    # Métricas completas
    accuracy = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average='weighted')
    precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
    recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)

    report = _convert_numpy_types(classification_report(y_test, y_pred, output_dict=True, zero_division=0))
    conf_matrix = confusion_matrix(y_test, y_pred)

    # Validação cruzada estratificada usando o PIPELINE (sem data leakage).
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_pipeline = build_ensemble_pipeline(is_imbalanced)
    cv_scores = cross_val_score(cv_pipeline, X, y, cv=cv, scoring='accuracy')
    cv_f1_scores = cross_val_score(cv_pipeline, X, y, cv=cv, scoring='f1_weighted')

    # ROC-AUC se possível
    roc_auc = None
    if y_pred_proba is not None and len(np.unique(y_test)) == 2:
        try:
            roc_auc = float(roc_auc_score(y_test, y_pred_proba))
        except ValueError:
            roc_auc = None

    # Importância das variáveis (do Random Forest dentro do ensemble do pipeline)
    rf_model = model.named_steps['ensemble'].named_estimators_['rf']
    feat_importances = pd.Series(rf_model.feature_importances_, index=feature_cols)

    distribuicao_classes = {int(k): int(v) for k, v in class_counts.to_dict().items()}

    response = {
        "acuracia": float(accuracy),
        "f1_score": float(f1),
        "precisao": float(precision),
        "recall": float(recall),
        "roc_auc": roc_auc,
        "relatorio_classificacao": report,
        "matriz_confusao": conf_matrix.tolist(),
        "validacao_cruzada": {
            "accuracy_scores": cv_scores.tolist(),
            "accuracy_mean": float(cv_scores.mean()),
            "accuracy_std": float(cv_scores.std()),
            "f1_scores": cv_f1_scores.tolist(),
            "f1_mean": float(cv_f1_scores.mean()),
            "f1_std": float(cv_f1_scores.std())
        },
        "importancia_variaveis": {k: float(v) for k, v in feat_importances.to_dict().items()},
        "configuracao": {
            "features_usadas": feature_cols,
            "total_features": len(feature_cols),
            "enhanced_features": bool(use_enhanced),
            "classe_desbalanceada": bool(is_imbalanced),
            "total_amostras": int(len(y)),
            "amostras_treino": int(len(y_train)),
            "amostras_teste": int(len(y_test)),
            "distribuicao_classes": distribuicao_classes
        }
    }

    return jsonify(response)


@analise_bp.route('/analise/graficos', methods=['GET'])
def analise_graficos():
    lat, lon = validar_coordenadas(
        request.args.get('lat', default=_DEFAULT_LAT),
        request.args.get('lon', default=_DEFAULT_LON),
    )
    use_enhanced = request.args.get('enhanced', default='true', type=str).lower() == 'true'

    X, y, feature_cols, is_imbalanced, _ = _preparar_dataset(lat, lon, use_enhanced)

    x_train, x_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = build_ensemble_pipeline(is_imbalanced)
    model.fit(x_train, y_train)

    y_pred = model.predict(x_test)
    conf_matrix = confusion_matrix(y_test, y_pred)

    rf_model = model.named_steps['ensemble'].named_estimators_['rf']
    feat_importances = pd.Series(rf_model.feature_importances_, index=feature_cols)

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    try:
        # Matriz de Confusão
        sns.heatmap(conf_matrix, annot=True, fmt='d', cmap='Blues', ax=axes[0])
        axes[0].set_title('Matriz de Confusão')
        axes[0].set_xlabel('Previsto')
        axes[0].set_ylabel('Real')

        # Gráfico de Importância das Variáveis
        feat_importances.sort_values().plot(kind='barh', ax=axes[1], color='teal')
        axes[1].set_title('Importância das Variáveis')
        axes[1].set_xlabel('Importância')

        # Validação Cruzada Scores (com pipeline, sem leakage)
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_scores = cross_val_score(build_ensemble_pipeline(is_imbalanced), X, y, cv=cv, scoring='accuracy')
        axes[2].bar(range(1, 6), cv_scores, color='steelblue', alpha=0.7)
        axes[2].axhline(y=cv_scores.mean(), color='red', linestyle='--', label=f'Média: {cv_scores.mean():.3f}')
        axes[2].set_title('Validação Cruzada (5-Fold)')
        axes[2].set_xlabel('Fold')
        axes[2].set_ylabel('Acurácia')
        axes[2].legend()
        axes[2].set_ylim([0, 1])

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        return send_file(buf, mimetype='image/png')
    finally:
        plt.close(fig)
