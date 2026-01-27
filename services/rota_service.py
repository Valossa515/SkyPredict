from datetime import datetime
import pandas as pd

from services.aeroapi_service import obter_coordenadas_aeroporto, obter_rotas_aeroporto
from services.meteostat_service import carregar_dados
from services.model_service import treinar_modelo, prever_variavel

FEATURES = ['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']

def _avaliar_risco_do_df(df: pd.DataFrame, data_futura: str):
    dia = pd.to_datetime(data_futura)

    if not isinstance(df.index, pd.DatetimeIndex):
        return None, None

    mask = df.index.normalize() == dia.normalize()
    if not mask.any():
        return None, None

    row = df.loc[mask].iloc[0]
    risk = int(row.get("risk", 0))
    score = int(row.get("risk_score", 0)) if pd.notna(row.get("risk_score")) else 0
    return risk, score

def _avaliar_risco_por_modelo(df: pd.DataFrame, data_futura: str, lat: float, lon: float):
    model = treinar_modelo(df, lat, lon)
    previsoes = {col: prever_variavel(df, col, data_futura, lat, lon) for col in FEATURES}
    risk = int(model.predict(pd.DataFrame(previsoes, index=[0]))[0])
    return risk, None

def gerar_sugestao_rota(origem_id, destino_id, data_futura):
    datetime.strptime(data_futura, '%Y-%m-%d')

    lat_origem, lon_origem = obter_coordenadas_aeroporto(origem_id)
    lat_destino, lon_destino = obter_coordenadas_aeroporto(destino_id)

    df_origem = carregar_dados(lat_origem, lon_origem)
    risco_origem, score_origem = _avaliar_risco_do_df(df_origem, data_futura)
    if risco_origem is None:
        risco_origem, score_origem = _avaliar_risco_por_modelo(df_origem, data_futura, lat_origem, lon_origem)

    df_destino = carregar_dados(lat_destino, lon_destino)
    risco_destino, score_destino = _avaliar_risco_do_df(df_destino, data_futura)
    if risco_destino is None:
        risco_destino, score_destino = _avaliar_risco_por_modelo(df_destino, data_futura, lat_destino, lon_destino)

    rotas = obter_rotas_aeroporto(origem_id, destino_id)

    sugestao = (
        "Evitar voo devido a alto risco meteorológico."
        if (risco_origem == 1 or risco_destino == 1)
        else "Rota segura. Risco meteorológico baixo."
    )

    payload = {
        "origem": origem_id,
        "destino": destino_id,
        "data": data_futura,
        "risco_origem": "Alto" if risco_origem == 1 else "Baixo",
        "risco_destino": "Alto" if risco_destino == 1 else "Baixo",
        "rotas": rotas,
        "sugestao": sugestao,
    }

    # ajuda MUITO no debug/explicação
    if score_origem is not None:
        payload["risk_score_origem"] = int(score_origem)
    if score_destino is not None:
        payload["risk_score_destino"] = int(score_destino)

    return payload