import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

# Fallback de dados meteorológicos (usado se o pacote meteostat falhar).
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"

# Configurações da API AeroAPI
AERO_API_URL = "https://aeroapi.flightaware.com/aeroapi"
AEROAPI_HEADERS = {
    "x-apikey": os.getenv("AEROAPI_KEY"),
}

# Features meteorológicas base (fonte única de verdade).
BASE_FEATURES = ['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']

# Janela de dados históricos consultada na Meteostat.
HISTORICAL_START_DATE = os.getenv("HISTORICAL_START_DATE", "2018-01-01")

# Mensagens e constantes
HISTORICAL_LABEL = 'Dados Históricos'
FUTURE_DATE_LABEL = 'Data Futura'
PREDICTION_LABEL = 'Previsão'
TEMPERATURE_UNIT = 'Temperatura (°C)'
DATE_FORMAT_MSG = 'Formato de data inválido. Use YYYY-MM-DD.'
