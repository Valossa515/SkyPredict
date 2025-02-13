import requests
from config import AERO_API_URL, AEROAPI_HEADERS

def obter_coordenadas_aeroporto(aeroporto_id):
    url = f"{AERO_API_URL}/airports/{aeroporto_id}"
    response = requests.get(url, headers=AEROAPI_HEADERS)
    if response.status_code == 200:
        data = response.json()
        return data['latitude'], data['longitude']
    raise ValueError(f"Erro ao obter coordenadas do aeroporto {aeroporto_id}: {response.status_code}")

def obter_rotas_aeroporto(origem_id, destino_id):
    url = f"{AERO_API_URL}/airports/{origem_id}/routes/{destino_id}"
    response = requests.get(url, headers=AEROAPI_HEADERS)
    if response.status_code == 200:
        return response.json()
    raise ValueError(f"Erro ao obter rotas entre {origem_id} e {destino_id}: {response.status_code}")
