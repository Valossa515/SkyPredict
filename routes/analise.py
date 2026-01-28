from flask import Blueprint, request, jsonify, send_file
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import io
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                            f1_score, precision_score, recall_score, roc_auc_score)
from services.meteostat_service import carregar_dados
from services.model_service import BASE_FEATURES, ENHANCED_FEATURES, _prepare_training_frame

analise_bp = Blueprint('analise', __name__)


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

@analise_bp.route('/analise', methods=['GET'])
def analise():
    lat = request.args.get('lat', default=-23.5505, type=float)
    lon = request.args.get('lon', default=-46.6333, type=float)
    use_enhanced = request.args.get('enhanced', default='true', type=str).lower() == 'true'

    try:
        df = carregar_dados(lat, lon)

        # Preparar dados com ou sem features derivadas
        frame = _prepare_training_frame(df, use_enhanced_features=use_enhanced)

        # Selecionar features baseado na configuração
        feature_cols = ENHANCED_FEATURES if use_enhanced else BASE_FEATURES
        feature_cols = [f for f in feature_cols if f in frame.columns]

        X = frame[feature_cols]
        y = frame['risk']

        # Verificar desbalanceamento
        class_counts = y.value_counts()
        is_imbalanced = len(class_counts) > 1 and (class_counts.min() / class_counts.max()) < 0.3
        class_weight = 'balanced' if is_imbalanced else None

        # Split estratificado
        x_train, x_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # Normalização
        scaler = StandardScaler()
        x_train_scaled = scaler.fit_transform(x_train)
        x_test_scaled = scaler.transform(x_test)

        # Modelo otimizado com ensemble
        rf = RandomForestClassifier(
            n_estimators=300, max_depth=15, min_samples_split=5,
            min_samples_leaf=2, max_features='sqrt',
            class_weight=class_weight, random_state=42, n_jobs=-1
        )
        gb = GradientBoostingClassifier(
            n_estimators=150, max_depth=5, learning_rate=0.1,
            min_samples_split=5, min_samples_leaf=2, random_state=42
        )
        model = VotingClassifier(
            estimators=[('rf', rf), ('gb', gb)],
            voting='soft', n_jobs=-1
        )
        model.fit(x_train_scaled, y_train)

        y_pred = model.predict(x_test_scaled)
        y_pred_proba = model.predict_proba(x_test_scaled)[:, 1] if hasattr(model, 'predict_proba') else None

        # Métricas completas
        accuracy = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, average='weighted')
        precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
        recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)

        report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
        # Converter tipos numpy no relatório
        report = _convert_numpy_types(report)
        conf_matrix = confusion_matrix(y_test, y_pred)

        # Validação cruzada estratificada
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_scores = cross_val_score(model, scaler.fit_transform(X), y, cv=cv, scoring='accuracy')
        cv_f1_scores = cross_val_score(model, scaler.fit_transform(X), y, cv=cv, scoring='f1_weighted')

        # ROC-AUC se possível
        roc_auc = None
        if y_pred_proba is not None and len(np.unique(y_test)) == 2:
            try:
                roc_auc = float(roc_auc_score(y_test, y_pred_proba))
            except:
                pass

        # Importância das variáveis (do Random Forest do ensemble)
        rf_model = model.named_estimators_['rf']
        feat_importances = pd.Series(rf_model.feature_importances_, index=feature_cols)

        # Converter distribuição de classes para tipos Python nativos
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

    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@analise_bp.route('/analise/graficos', methods=['GET'])
def analise_graficos():
    lat = request.args.get('lat', default=-23.5505, type=float)
    lon = request.args.get('lon', default=-46.6333, type=float)
    use_enhanced = request.args.get('enhanced', default='true', type=str).lower() == 'true'

    try:
        df = carregar_dados(lat, lon)

        # Preparar dados com ou sem features derivadas
        frame = _prepare_training_frame(df, use_enhanced_features=use_enhanced)

        # Selecionar features
        feature_cols = ENHANCED_FEATURES if use_enhanced else BASE_FEATURES
        feature_cols = [f for f in feature_cols if f in frame.columns]

        X = frame[feature_cols]
        y = frame['risk']

        # Verificar desbalanceamento
        class_counts = y.value_counts()
        is_imbalanced = len(class_counts) > 1 and (class_counts.min() / class_counts.max()) < 0.3
        class_weight = 'balanced' if is_imbalanced else None

        x_train, x_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # Normalização
        scaler = StandardScaler()
        x_train_scaled = scaler.fit_transform(x_train)
        x_test_scaled = scaler.transform(x_test)

        # Modelo otimizado
        rf = RandomForestClassifier(
            n_estimators=300, max_depth=15, min_samples_split=5,
            min_samples_leaf=2, max_features='sqrt',
            class_weight=class_weight, random_state=42, n_jobs=-1
        )
        gb = GradientBoostingClassifier(
            n_estimators=150, max_depth=5, learning_rate=0.1,
            min_samples_split=5, min_samples_leaf=2, random_state=42
        )
        model = VotingClassifier(
            estimators=[('rf', rf), ('gb', gb)],
            voting='soft', n_jobs=-1
        )
        model.fit(x_train_scaled, y_train)

        y_pred = model.predict(x_test_scaled)
        conf_matrix = confusion_matrix(y_test, y_pred)

        # Importância das variáveis do Random Forest
        rf_model = model.named_estimators_['rf']
        feat_importances = pd.Series(rf_model.feature_importances_, index=feature_cols)

        # Criar figura com 3 subplots
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))

        # Matriz de Confusão
        sns.heatmap(conf_matrix, annot=True, fmt='d', cmap='Blues', ax=axes[0])
        axes[0].set_title('Matriz de Confusão')
        axes[0].set_xlabel('Previsto')
        axes[0].set_ylabel('Real')

        # Gráfico de Importância das Variáveis
        feat_importances.sort_values().plot(kind='barh', ax=axes[1], color='teal')
        axes[1].set_title('Importância das Variáveis')
        axes[1].set_xlabel('Importância')

        # Validação Cruzada Scores
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_scores = cross_val_score(model, scaler.fit_transform(X), y, cv=cv, scoring='accuracy')
        axes[2].bar(range(1, 6), cv_scores, color='steelblue', alpha=0.7)
        axes[2].axhline(y=cv_scores.mean(), color='red', linestyle='--', label=f'Média: {cv_scores.mean():.3f}')
        axes[2].set_title('Validação Cruzada (5-Fold)')
        axes[2].set_xlabel('Fold')
        axes[2].set_ylabel('Acurácia')
        axes[2].legend()
        axes[2].set_ylim([0, 1])

        plt.tight_layout()

        # Salvar e retornar a imagem
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        plt.close()

        return send_file(buf, mimetype='image/png')

    except Exception as e:
        return jsonify({"erro": str(e)}), 500
