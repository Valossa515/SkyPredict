import re
from urllib.parse import quote

from services.http_client import session
from config import AERO_API_URL, AEROAPI_HEADERS

# Códigos IATA (3) / ICAO (4) e alguns identificadores locais são alfanuméricos.
_AIRPORT_ID_RE = re.compile(r"^[A-Za-z0-9]{3,4}$")


def _validar_aeroporto_id(aeroporto_id):
    if not aeroporto_id or not _AIRPORT_ID_RE.match(str(aeroporto_id)):
        raise ValueError(
            f"Identificador de aeroporto inválido: {aeroporto_id!r}. "
            "Use um código IATA (3 letras) ou ICAO (4 letras)."
        )
    return str(aeroporto_id).upper()


def obter_coordenadas_aeroporto(aeroporto_id):
    aeroporto_id = _validar_aeroporto_id(aeroporto_id)
    url = f"{AERO_API_URL}/airports/{quote(aeroporto_id)}"
    response = session.get(url, headers=AEROAPI_HEADERS, timeout=30)
    response.raise_for_status()

    data = response.json()

    # AeroAPI costuma retornar latitude/longitude direto no payload do aeroporto.
    lat = data.get("latitude")
    lon = data.get("longitude")

    if lat is None or lon is None:
        raise ValueError(f"Resposta da AeroAPI sem latitude/longitude para {aeroporto_id}: {list(data.keys())}")

    return float(lat), float(lon)


def obter_rotas_aeroporto(origem_id, destino_id):
    origem_id = _validar_aeroporto_id(origem_id)
    destino_id = _validar_aeroporto_id(destino_id)
    url = f"{AERO_API_URL}/airports/{quote(origem_id)}/routes/{quote(destino_id)}"
    response = session.get(url, headers=AEROAPI_HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()
