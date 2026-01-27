from services.http_client import session
from config import AERO_API_URL, AEROAPI_HEADERS

def obter_coordenadas_aeroporto(aeroporto_id):
    url = f"{AERO_API_URL}/airports/{aeroporto_id}"
    response = session.get(url, headers=AEROAPI_HEADERS, timeout=30, verify=False)  # <- sem verify=False
    response.raise_for_status()

    data = response.json()

    # AeroAPI costuma retornar latitude/longitude direto no payload do aeroporto.
    # Ajuste as chaves se no seu JSON estiver diferente.
    lat = data.get("latitude")
    lon = data.get("longitude")

    if lat is None or lon is None:
        raise ValueError(f"Resposta da AeroAPI sem latitude/longitude para {aeroporto_id}: {list(data.keys())}")

    return float(lat), float(lon)


def obter_rotas_aeroporto(origem_id, destino_id):
    url = f"{AERO_API_URL}/airports/{origem_id}/routes/{destino_id}"
    response = session.get(url, headers=AEROAPI_HEADERS, timeout=30, verify=False)  # <- sem verify=False
    response.raise_for_status()
    return response.json()

