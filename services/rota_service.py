from datetime import datetime
import pandas as pd

from services.aeroapi_service import obter_coordenadas_aeroporto, obter_rotas_aeroporto
from services.meteostat_service import carregar_dados
from services.model_service import treinar_modelo, prever_variavel


def gerar_sugestao_rota(origem_id, destino_id, data_futura):
    datetime.strptime(data_futura, '%Y-%m-%d')

    lat_origem, lon_origem = obter_coordenadas_aeroporto(origem_id)
    lat_destino, lon_destino = obter_coordenadas_aeroporto(destino_id)

    df_origem = carregar_dados(lat_origem, lon_origem)
    model_origem = treinar_modelo(df_origem, lat_origem, lon_origem)

    previsoes_origem = {
        coluna: prever_variavel(df_origem, coluna, data_futura, lat_origem, lon_origem)
        for coluna in ['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']
    }
    risco_origem = model_origem.predict(pd.DataFrame(previsoes_origem, index=[0]))[0]

    df_destino = carregar_dados(lat_destino, lon_destino)
    model_destino = treinar_modelo(df_destino, lat_destino, lon_destino)

    previsoes_destino = {
        coluna: prever_variavel(df_destino, coluna, data_futura, lat_destino, lon_destino)
        for coluna in ['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']
    }
    risco_destino = model_destino.predict(pd.DataFrame(previsoes_destino, index=[0]))[0]

    rotas = obter_rotas_aeroporto(origem_id, destino_id)

    if risco_origem == 1 or risco_destino == 1:
        sugestao = "Evitar voo devido a alto risco meteorológico."
    else:
        sugestao = "Rota segura. Risco meteorológico baixo."

    return {
        "origem": origem_id,
        "destino": destino_id,
        "data": data_futura,
        "risco_origem": "Alto" if risco_origem == 1 else "Baixo",
        "risco_destino": "Alto" if risco_destino == 1 else "Baixo",
        "rotas": rotas,
        "sugestao": sugestao,
    }
