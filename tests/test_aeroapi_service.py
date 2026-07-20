import pytest

from services.aeroapi_service import _validar_aeroporto_id


@pytest.mark.parametrize("valido", ["GRU", "jfk", "SBGR", "kjfk"])
def test_ids_validos(valido):
    assert _validar_aeroporto_id(valido) == valido.upper()


@pytest.mark.parametrize("invalido", ["", "A", "AB", "ABCDE", "GR/", "../etc", "G U", None])
def test_ids_invalidos(invalido):
    with pytest.raises(ValueError):
        _validar_aeroporto_id(invalido)
