from flask import Blueprint, request, jsonify
import pandas as pd
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from services.meteostat_service import carregar_dados

analise_bp = Blueprint('analise', __name__)

@analise_bp.route('/analise', methods=['GET'])
def analise():
    lat = request.args.get('lat', default=-23.5505, type=float)
    lon = request.args.get('lon', default=-46.6333, type=float)

    try:
        df = carregar_dados(lat, lon)

        X = df[['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']]
        y = df['risk']
        x_train, x_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        model = RandomForestClassifier(n_estimators=100, random_state=42, min_samples_leaf=1, max_features='sqrt')
        model.fit(x_train, y_train)

        y_pred = model.predict(x_test)
        accuracy = accuracy_score(y_test, y_pred)
        report = classification_report(y_test, y_pred, output_dict=True)
        conf_matrix = confusion_matrix(y_test, y_pred)
        cv_scores = cross_val_score(model, X, y, cv=5, scoring='accuracy')
        feat_importances = pd.Series(model.feature_importances_, index=X.columns)

        return jsonify({
            "acuracia": accuracy,
            "relatorio_classificacao": report,
            "matriz_confusao": conf_matrix.tolist(),
            "validacao_cruzada": cv_scores.tolist(),
            "importancia_variaveis": feat_importances.to_dict()
        })

    except Exception as e:
        return jsonify({"erro": str(e)}), 500
