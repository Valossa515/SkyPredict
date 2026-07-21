from datetime import datetime
import pandas as pd

from services.aeroapi_service import obter_coordenadas_aeroporto, obter_rotas_aeroporto
from services.meteostat_service import carregar_dados
from services.model_service import treinar_modelo, prever_variavel, prever_com_modelo, BASE_FEATURES

FEATURES = BASE_FEATURES

def _avaliar_risco_do_df(df: pd.DataFrame, data_futura: str):
    dia = pd.to_datetime(data_futura)

    if not isinstance(df.index, pd.DatetimeIndex):
        return None, None

    # Cast explícito para DatetimeIndex para type checker
    idx: pd.DatetimeIndex = df.index  # type: ignore[assignment]
    mask = idx.normalize() == dia.normalize()
    if not mask.any():
        return None, None

    row = df.loc[mask].iloc[0]
    risk = int(row.get("risk", 0))
    score = int(row.get("risk_score", 0)) if pd.notna(row.get("risk_score")) else 0
    return risk, score

def _avaliar_risco_por_modelo(df: pd.DataFrame, data_futura: str, lat: float, lon: float):
    model = treinar_modelo(df, lat, lon)
    previsoes = {col: prever_variavel(df, col, data_futura, lat, lon) for col in FEATURES}
    # Usar a função prever_com_modelo que aplica as transformações corretas
    risk = int(prever_com_modelo(previsoes, model, lat, lon, data_futura)[0])
    return risk, None

def _avaliar_risco(lat, lon, data_futura):
    df = carregar_dados(lat, lon)
    risco, score = _avaliar_risco_do_df(df, data_futura)
    if risco is None:
        risco, score = _avaliar_risco_por_modelo(df, data_futura, lat, lon)
    return risco, score


def _rotulo_risco(risco):
    if risco == 1:
        return "Alto"
    if risco == 0:
        return "Baixo"
    return "Indisponível"


def gerar_sugestao_rota(origem_id, destino_id, data_futura,
                        coord_resolver=None, rotas_provider=None,
                        risco_resiliente=False):
    """Gera a sugestão de rota com avaliação de risco meteorológico.

    Por padrão usa a AeroAPI para coordenadas e rotas. Os parâmetros
    ``coord_resolver`` e ``rotas_provider`` permitem injetar outras fontes
    (ex.: base local de aeroportos), o que habilita um modo offline/demo sem
    depender da AeroAPI. Com ``risco_resiliente=True``, falhas ao obter os
    dados meteorológicos não interrompem a resposta — o risco fica
    "Indisponível" e o restante (rota, aeroportos) continua sendo retornado.
    """
    coord_resolver = coord_resolver or obter_coordenadas_aeroporto
    rotas_provider = rotas_provider or obter_rotas_aeroporto

    datetime.strptime(data_futura, '%Y-%m-%d')

    lat_origem, lon_origem = coord_resolver(origem_id)
    lat_destino, lon_destino = coord_resolver(destino_id)

    try:
        risco_origem, score_origem = _avaliar_risco(lat_origem, lon_origem, data_futura)
        risco_destino, score_destino = _avaliar_risco(lat_destino, lon_destino, data_futura)
    except Exception:
        if not risco_resiliente:
            raise
        risco_origem = risco_destino = None
        score_origem = score_destino = None

    rotas = rotas_provider(origem_id, destino_id)

    if risco_origem == 1 or risco_destino == 1:
        sugestao = "Evitar voo devido a alto risco meteorológico."
    elif risco_origem is None and risco_destino is None:
        sugestao = "Risco meteorológico indisponível (dados climáticos não obtidos)."
    else:
        sugestao = "Rota segura. Risco meteorológico baixo."

    payload = {
        "origem": origem_id,
        "destino": destino_id,
        "data": data_futura,
        "risco_origem": _rotulo_risco(risco_origem),
        "risco_destino": _rotulo_risco(risco_destino),
        "rotas": rotas,
        "sugestao": sugestao,
    }

    # ajuda MUITO no debug/explicação
    if score_origem is not None:
        payload["risk_score_origem"] = int(score_origem)
    if score_destino is not None:
        payload["risk_score_destino"] = int(score_destino)

    return payload