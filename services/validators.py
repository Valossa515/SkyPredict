"""Validações reutilizáveis de parâmetros de entrada da API."""
from datetime import datetime

from config import DATE_FORMAT_MSG


class ValidationError(ValueError):
    """Erro de validação de entrada (deve resultar em HTTP 400)."""


def validar_coordenadas(lat, lon):
    """Valida latitude/longitude e retorna-as como float.

    Levanta ValidationError se ausentes ou fora dos limites geográficos.
    """
    if lat is None or lon is None:
        raise ValidationError("Os parâmetros 'lat' e 'lon' são obrigatórios.")
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        raise ValidationError("'lat' e 'lon' devem ser numéricos.")

    if not (-90.0 <= lat <= 90.0):
        raise ValidationError("'lat' deve estar entre -90 e 90.")
    if not (-180.0 <= lon <= 180.0):
        raise ValidationError("'lon' deve estar entre -180 e 180.")

    return lat, lon


def validar_data(data_str):
    """Valida uma data no formato YYYY-MM-DD e retorna a string original."""
    if not data_str:
        raise ValidationError("O parâmetro 'data' é obrigatório.")
    try:
        datetime.strptime(data_str, "%Y-%m-%d")
    except ValueError:
        raise ValidationError(DATE_FORMAT_MSG)
    return data_str
