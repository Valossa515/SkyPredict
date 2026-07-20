import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configurações da API Meteostat
API_URL = "https://meteostat.p.rapidapi.com/point/daily"
MONGO_URI = os.getenv("MONGO_URI")
HEADERS = {
    "X-RapidAPI-Key": os.getenv("METEOSTAT_API_KEY"),
    "X-RapidAPI-Host": os.getenv("METEOSTAT_API_HOST")
}

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
