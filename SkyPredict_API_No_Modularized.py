from flask import Flask, request, jsonify, send_file
import requests
import pandas as pd
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
from prophet import Prophet
import matplotlib.pyplot as plt
import seaborn as sns
import io
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# ============================
# Constantes para strings usadas em múltiplos locais
# ============================
HISTORICAL_LABEL = 'Dados Históricos'
FUTURE_DATE_LABEL = 'Data Futura'
PREDICTION_LABEL = 'Previsão'
TEMPERATURE_UNIT = 'Temperatura (°C)'
DATE_FORMAT_MSG = 'Formato de data inválido. Use YYYY-MM-DD.'

# ============================
# Configurações da API Meteostat
# ============================
API_URL = "https://meteostat.p.rapidapi.com/point/monthly"
HEADERS = {
    "X-RapidAPI-Key": os.getenv("METEOSTAT_API_KEY"),
    "X-RapidAPI-Host": os.getenv("METEOSTAT_API_HOST")
}

# ============================
# Configurações da API AeroAPI
# ============================
AERO_API_URL = "https://aeroapi.flightaware.com/aeroapi"
AEROAPI_HEADERS = {
    "x-apikey": os.getenv("AEROAPI_KEY"),
}

# Função para carregar e preparar os dados
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
        # Limpeza da base de dados: remover linhas com dados ausentes
        df = df.dropna(subset=['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres'])
    else:
        raise ValueError("Erro ao obter dados da API Meteostat.")

    # Criar variável de risco
    df['risk'] = df.apply(lambda row: 1 if row['tmax'] >
                          35 or row['prcp'] > 50 or row['wspd'] > 25 else 0, axis=1)

    # Treinar modelo de classificação com parâmetros explícitos
    X = df[['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']]
    y = df['risk']
    model = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
        min_samples_leaf=1,
        max_features='sqrt'
    )
    model.fit(X, y)

    return df, model

# Função para prever variáveis meteorológicas usando Prophet
def prever_variavel(df, coluna, data_futura):
    prophet_df = df[[coluna]].reset_index()
    prophet_df.columns = ['ds', 'y']
    modelo = Prophet()
    modelo.fit(prophet_df)
    futuro = pd.DataFrame({'ds': [data_futura]})
    previsao = modelo.predict(futuro)
    return previsao['yhat'].values[0]


def obter_coodernadas_aeroporto(aeroporto_id):
    url = f"{AERO_API_URL}/airports/{aeroporto_id}"
    response = requests.get(url, headers=AEROAPI_HEADERS)
    if response.status_code == 200:
        data = response.json()
        return data['latitude'], data['longitude']
    else:
        raise ValueError(
            f"Erro ao obter coordenadas do aeroporto {aeroporto_id}: {response.status_code}")


def obter_rotas_aeroporto(origem_id, destino_id):
    url = f"{AERO_API_URL}/airports/{origem_id}/routes/{destino_id}"
    response = requests.get(url, headers=AEROAPI_HEADERS)
    if response.status_code == 200:
        return response.json()
    else:
        raise ValueError(
            f"Erro ao obter rotas entre {origem_id} e {destino_id}: {response.status_code}")


# Inicializar o Flask
app = Flask(__name__)


@app.route('/sugerir_rota', methods=['GET'])
def sugerir_rota():
    origem_id = request.args.get('origem_id')
    destino_id = request.args.get('destino_id')
    data_futura = request.args.get('data')

    if not origem_id or not destino_id or not data_futura:
        return jsonify({"erro": "Os parâmetros 'origem_id', 'destino_id' e 'data' são obrigatórios."}), 400

    try:
        datetime.strptime(data_futura, '%Y-%m-%d')
    except ValueError:
        return jsonify({"erro": DATE_FORMAT_MSG}), 400

    try:
        # Obter coordenadas dos aeroportos
        lat_origem, lon_origem = obter_coodernadas_aeroporto(origem_id)
        lat_destino, lon_destino = obter_coodernadas_aeroporto(destino_id)

        # Calcular risco para a origem
        df_origem, model_origem = carregar_dados(lat_origem, lon_origem)
        previsoes_origem = {coluna: prever_variavel(df_origem, coluna, data_futura)
                            for coluna in ['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']}
        dados_futuros_origem = pd.DataFrame(previsoes_origem, index=[0])
        risco_origem = model_origem.predict(dados_futuros_origem)[0]

        # Calcular risco para o destino
        df_destino, model_destino = carregar_dados(lat_destino, lon_destino)
        previsoes_destino = {coluna: prever_variavel(df_destino, coluna, data_futura)
                             for coluna in ['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']}
        dados_futuros_destino = pd.DataFrame(previsoes_destino, index=[0])
        risco_destino = model_destino.predict(dados_futuros_destino)[0]

        # Obter rotas entre os aeroportos
        rotas = obter_rotas_aeroporto(origem_id, destino_id)

        # Sugerir rota com base no risco
        if risco_origem == 1 or risco_destino == 1:
            sugestao = "Evitar voo devido a alto risco meteorologico."
        else:
            sugestao = "Rota segura. Risco meteorologico baixo."

        resposta = {
            "origem": origem_id,
            "destino": destino_id,
            "data": data_futura,
            "risco_origem": "Alto" if risco_origem == 1 else "Baixo",
            "risco_destino": "Alto" if risco_destino == 1 else "Baixo",
            "rotas": rotas,
            "sugestao": sugestao
        }
        return jsonify(resposta)

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# Endpoint para previsão
@app.route('/previsao', methods=['GET'])
def previsao():
    # Obter parâmetros da requisição
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    data_futura = request.args.get('data')

    if not lat or not lon or not data_futura:
        return jsonify({"erro": "Os parâmetros 'lat', 'lon' e 'data' são obrigatórios."}), 400

    try:
        datetime.strptime(data_futura, '%Y-%m-%d')
    except ValueError:
        return jsonify({"erro": "Formato de data inválido. Use YYYY-MM-DD."}), 400

    try:
        df, model = carregar_dados(lat, lon)

        # Previsões para as variáveis meteorológicas
        previsoes = {coluna: prever_variavel(df, coluna, data_futura)
                     for coluna in ['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']}

        # Previsão de risco
        dados_futuros = pd.DataFrame(previsoes, index=[0])
        previsao_risco = model.predict(dados_futuros)[0]

        resposta = {
            "localizacao": {"latitude": lat, "longitude": lon},
            "data": data_futura,
            "previsao": previsoes,
            "risco": "Alto" if previsao_risco == 1 else "Baixo"
        }
        return jsonify(resposta)

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# Endpoint para gráficos
@app.route('/graficos', methods=['GET'])
def graficos():
    # Obter a data da requisição
    data_futura = request.args.get('data')
    if not data_futura:
        return jsonify({"erro": "O parâmetro 'data' é obrigatório (formato YYYY-MM-DD)."}), 400

    try:
        # Validar a data
        datetime.strptime(data_futura, '%Y-%m-%d')
    except ValueError:
        return jsonify({"erro": "Formato de data inválido. Use YYYY-MM-DD."}), 400

    # Obter parâmetros da requisição
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)

    if not lat or not lon:
        return jsonify({"erro": "Os parâmetros 'lat' e 'lon' são obrigatórios."}), 400

    try:
        df, _ = carregar_dados(lat, lon)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    # Prever cada variável meteorológica
    tavg_futuro = prever_variavel(df, 'tavg', data_futura)
    tmin_futuro = prever_variavel(df, 'tmin', data_futura)
    tmax_futuro = prever_variavel(df, 'tmax', data_futura)
    prcp_futuro = prever_variavel(df, 'prcp', data_futura)
    wspd_futuro = prever_variavel(df, 'wspd', data_futura)
    pres_futuro = prever_variavel(df, 'pres', data_futura)

    # Criar os gráficos
    plt.figure(figsize=(15, 10))

    # Gráfico de temperatura média (tavg)
    plt.subplot(3, 2, 1)
    plt.plot(df.index, df['tavg'], label=HISTORICAL_LABEL)
    plt.axvline(pd.to_datetime(data_futura), color='red',
                linestyle='--', label=FUTURE_DATE_LABEL)
    plt.scatter(pd.to_datetime(data_futura), tavg_futuro,
                color='green', label=PREDICTION_LABEL)
    plt.title('Temperatura Média (tavg)')
    plt.xlabel('Data')
    plt.ylabel(TEMPERATURE_UNIT)
    plt.legend()

    # Gráfico de temperatura mínima (tmin)
    plt.subplot(3, 2, 2)
    plt.plot(df.index, df['tmin'], label=HISTORICAL_LABEL)
    plt.axvline(pd.to_datetime(data_futura), color='red',
                linestyle='--', label=FUTURE_DATE_LABEL)
    plt.scatter(pd.to_datetime(data_futura), tmin_futuro,
                color='green', label=PREDICTION_LABEL)
    plt.title('Temperatura Mínima (tmin)')
    plt.xlabel('Data')
    plt.ylabel(TEMPERATURE_UNIT)
    plt.legend()

    # Gráfico de temperatura máxima (tmax)
    plt.subplot(3, 2, 3)
    plt.plot(df.index, df['tmax'], label=HISTORICAL_LABEL)
    plt.axvline(pd.to_datetime(data_futura), color='red',
                linestyle='--', label=FUTURE_DATE_LABEL)
    plt.scatter(pd.to_datetime(data_futura), tmax_futuro,
                color='green', label=PREDICTION_LABEL)
    plt.title('Temperatura Máxima (tmax)')
    plt.xlabel('Data')
    plt.ylabel(TEMPERATURE_UNIT)
    plt.legend()

    # Gráfico de precipitação (prcp)
    plt.subplot(3, 2, 4)
    plt.plot(df.index, df['prcp'], label=HISTORICAL_LABEL)
    plt.axvline(pd.to_datetime(data_futura), color='red',
                linestyle='--', label=FUTURE_DATE_LABEL)
    plt.scatter(pd.to_datetime(data_futura), prcp_futuro,
                color='green', label=PREDICTION_LABEL)
    plt.title('Precipitação (prcp)')
    plt.xlabel('Data')
    plt.ylabel('Precipitação (mm)')
    plt.legend()

    # Gráfico de velocidade do vento (wspd)
    plt.subplot(3, 2, 5)
    plt.plot(df.index, df['wspd'], label=HISTORICAL_LABEL)
    plt.axvline(pd.to_datetime(data_futura), color='red',
                linestyle='--', label=FUTURE_DATE_LABEL)
    plt.scatter(pd.to_datetime(data_futura), wspd_futuro,
                color='green', label=PREDICTION_LABEL)
    plt.title('Velocidade do Vento (wspd)')
    plt.xlabel('Data')
    plt.ylabel('Velocidade do Vento (m/s)')
    plt.legend()

    # Gráfico de pressão atmosférica (pres)
    plt.subplot(3, 2, 6)
    plt.plot(df.index, df['pres'], label=HISTORICAL_LABEL)
    plt.axvline(pd.to_datetime(data_futura), color='red',
                linestyle='--', label=FUTURE_DATE_LABEL)
    plt.scatter(pd.to_datetime(data_futura), pres_futuro,
                color='green', label=PREDICTION_LABEL)
    plt.title('Pressão Atmosférica (pres)')
    plt.xlabel('Data')
    plt.ylabel('Pressão (hPa)')
    plt.legend()

    plt.tight_layout()

    # Salvar o gráfico em um buffer de memória
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()

    # Retornar a imagem
    return send_file(buf, mimetype='image/png')

# Endpoint para análise do modelo
@app.route('/analise', methods=['GET'])
def analise():
    # Obter os parâmetros da requisição
    lat = request.args.get('lat', default=-23.5505, type=float)
    lon = request.args.get('lon', default=-46.6333, type=float)

    try:
        df, _ = carregar_dados(lat, lon)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    # Treinar o modelo de classificação de risco com parâmetros explícitos
    X = df[['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']]
    y = df['risk']
    x_train, x_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42)
    model_local = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
        min_samples_leaf=1,
        max_features='sqrt'
    )
    model_local.fit(x_train, y_train)

    # Avaliação do modelo
    y_pred = model_local.predict(x_test)
    accuracy = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, output_dict=True)
    conf_matrix = confusion_matrix(y_test, y_pred)

    # Validação cruzada
    cv_scores = cross_val_score(model_local, X, y, cv=5, scoring='accuracy')

    # Importância das variáveis
    feat_importances = pd.Series(
        model_local.feature_importances_, index=X.columns)

    # Retornar a análise em JSON
    resposta = {
        "acuracia": accuracy,
        "relatorio_classificacao": report,
        "matriz_confusao": conf_matrix.tolist(),
        "validacao_cruzada": cv_scores.tolist(),
        "importancia_variaveis": feat_importances.to_dict()
    }
    return jsonify(resposta)

# -------------------------------
# Novo endpoint para exportar os dados para Excel
# -------------------------------
@app.route('/exportar_excel', methods=['GET'])
def exportar_excel():
    # Obter parâmetros da requisição
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)

    if not lat or not lon:
        return jsonify({"erro": "Os parâmetros 'lat' e 'lon' são obrigatórios."}), 400

    try:
        df, _ = carregar_dados(lat, lon)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    output = io.BytesIO()
    # Cria um objeto ExcelWriter usando o openpyxl
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=True, sheet_name='Dados')
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='dados_meteorologicos.xlsx'
    )

# Iniciar a API
if __name__ == '__main__':
    app.run(debug=True)
