import pytest

from services.validators import validar_coordenadas, validar_data, ValidationError


def test_validar_coordenadas_ok():
    assert validar_coordenadas("-23.55", "-46.63") == (-23.55, -46.63)
    assert validar_coordenadas(0, 0) == (0.0, 0.0)


def test_validar_coordenadas_ausentes():
    with pytest.raises(ValidationError):
        validar_coordenadas(None, None)


def test_validar_coordenadas_nao_numericas():
    with pytest.raises(ValidationError):
        validar_coordenadas("abc", "0")


@pytest.mark.parametrize("lat,lon", [(91, 0), (-91, 0), (0, 181), (0, -181)])
def test_validar_coordenadas_fora_dos_limites(lat, lon):
    with pytest.raises(ValidationError):
        validar_coordenadas(lat, lon)


def test_validar_data_ok():
    assert validar_data("2024-10-15") == "2024-10-15"


@pytest.mark.parametrize("valor", ["", None, "15/10/2024", "2024-13-01", "xx"])
def test_validar_data_invalida(valor):
    with pytest.raises(ValidationError):
        validar_data(valor)
