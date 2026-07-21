"""Orquestrador de provedores meteorológicos com fallback automático.

Seleciona a fonte de dados climáticos conforme ``WEATHER_PROVIDER``:
- ``auto`` (padrão): usa Meteostat se ``METEOSTAT_API_KEY`` estiver configurada
  e, em caso de falha, cai automaticamente para a Open-Meteo (sem chave).
  Sem a chave do Meteostat, usa direto a Open-Meteo.
- ``meteostat``: usa apenas o Meteostat.
- ``openmeteo``: usa apenas a Open-Meteo.

Todos os provedores retornam o mesmo DataFrame padronizado (via
``finalizar_clima``), então o restante da aplicação não muda.
"""
import logging
import os

from services import meteostat_service, openmeteo_service
from services.weather_common import FEATURES  # re-exportado por conveniência

__all__ = ["carregar_dados", "FEATURES"]

logger = logging.getLogger(__name__)

_PROVIDERS = {
    "meteostat": meteostat_service.carregar_dados,
    "openmeteo": openmeteo_service.carregar_dados,
}


def _ordem_provedores():
    provider = os.getenv("WEATHER_PROVIDER", "auto").lower()

    if provider in _PROVIDERS:
        return [provider]

    # auto: Meteostat (se houver chave) com fallback para Open-Meteo.
    if os.getenv("METEOSTAT_API_KEY"):
        return ["meteostat", "openmeteo"]
    return ["openmeteo"]


def carregar_dados(lat, lon):
    """Carrega dados climáticos tentando os provedores em ordem, com fallback."""
    ordem = _ordem_provedores()
    erros = []

    for nome in ordem:
        try:
            df = _PROVIDERS[nome](lat, lon)
            if len(ordem) > 1 and nome != ordem[0]:
                logger.info("Dados climáticos obtidos via fallback: %s", nome)
            return df
        except Exception as exc:  # noqa: BLE001 - registra e tenta o próximo provedor
            logger.warning("Provedor '%s' falhou (%s); tentando o próximo...", nome, exc)
            erros.append(f"{nome}: {exc}")

    raise ValueError(
        "Não foi possível obter dados meteorológicos de nenhum provedor. "
        + " | ".join(erros)
    )
