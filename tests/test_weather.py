import pandas as pd
import pytest

from services import openmeteo_service, weather_service
from services.weather_common import finalizar_clima, FEATURES


class _FakeResponse:
    def __init__(self, payload, ok=True, status_code=200, text=""):
        self._payload = payload
        self.ok = ok
        self.status_code = status_code
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _sample_openmeteo_payload():
    return {
        "daily": {
            "time": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "temperature_2m_mean": [22.0, 39.5, 25.0],
            "temperature_2m_min": [18.0, 30.0, 20.0],
            "temperature_2m_max": [28.0, 41.0, 30.0],   # dia 2: calor extremo
            "precipitation_sum": [0.0, 90.0, 5.0],       # dia 2: chuva forte
            "windspeed_10m_max": [10.0, 65.0, 12.0],     # dia 2: vento forte
        }
    }


# ---------- finalizar_clima (lógica compartilhada) ----------

def test_finalizar_clima_calcula_risco_e_fallback_pres():
    df = pd.DataFrame(
        {
            "tavg": [22.0, 39.5],
            "tmin": [18.0, 30.0],
            "tmax": [28.0, 41.0],
            "prcp": [0.0, 90.0],
            "wspd": [10.0, 65.0],
            # sem 'pres' de propósito -> deve cair no fallback
        },
        index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
    )
    out = finalizar_clima(df, fonte="teste")
    assert set(FEATURES).issubset(out.columns)
    assert "risk" in out.columns and "risk_score" in out.columns
    # pressão ausente -> fallback neutro
    assert (out["pres"] == 1013.25).all()
    # dia extremo deve ser risco alto
    assert int(out.loc["2024-01-02", "risk"]) == 1


# ---------- Open-Meteo provider ----------

def test_openmeteo_parseia_payload(monkeypatch):
    monkeypatch.setattr(
        openmeteo_service.session, "get",
        lambda *a, **k: _FakeResponse(_sample_openmeteo_payload()),
    )
    df = openmeteo_service.carregar_dados(-23.55, -46.63)
    assert list(df.index.strftime("%Y-%m-%d")) == ["2024-01-01", "2024-01-02", "2024-01-03"]
    assert int(df.loc["2024-01-02", "risk"]) == 1   # dia extremo
    assert int(df.loc["2024-01-01", "risk"]) == 0
    # mapeamento correto
    assert df.loc["2024-01-02", "tmax"] == 41.0
    assert df.loc["2024-01-02", "wspd"] == 65.0


def test_openmeteo_erro_http(monkeypatch):
    monkeypatch.setattr(
        openmeteo_service.session, "get",
        lambda *a, **k: _FakeResponse(None, ok=False, status_code=503, text="indisponível"),
    )
    with pytest.raises(ValueError):
        openmeteo_service.carregar_dados(0, 0)


def test_openmeteo_daily_vazio(monkeypatch):
    monkeypatch.setattr(
        openmeteo_service.session, "get",
        lambda *a, **k: _FakeResponse({"daily": {"time": []}}),
    )
    with pytest.raises(ValueError):
        openmeteo_service.carregar_dados(0, 0)


# ---------- Dispatcher com fallback ----------

def test_dispatcher_usa_openmeteo_sem_chave_meteostat(monkeypatch):
    monkeypatch.delenv("METEOSTAT_API_KEY", raising=False)
    monkeypatch.setenv("WEATHER_PROVIDER", "auto")
    monkeypatch.setitem(weather_service._PROVIDERS, "openmeteo", lambda lat, lon: "OPENMETEO_DF")
    assert weather_service.carregar_dados(0, 0) == "OPENMETEO_DF"


def test_dispatcher_cai_para_fallback_quando_primario_falha(monkeypatch):
    monkeypatch.setenv("METEOSTAT_API_KEY", "x")
    monkeypatch.setenv("WEATHER_PROVIDER", "auto")

    def _falha(lat, lon):
        raise ValueError("meteostat 403")

    monkeypatch.setitem(weather_service._PROVIDERS, "meteostat", _falha)
    monkeypatch.setitem(weather_service._PROVIDERS, "openmeteo", lambda lat, lon: "FALLBACK_DF")
    assert weather_service.carregar_dados(0, 0) == "FALLBACK_DF"


def test_dispatcher_erro_quando_todos_falham(monkeypatch):
    monkeypatch.setenv("WEATHER_PROVIDER", "openmeteo")

    def _falha(lat, lon):
        raise ValueError("boom")

    monkeypatch.setitem(weather_service._PROVIDERS, "openmeteo", _falha)
    with pytest.raises(ValueError):
        weather_service.carregar_dados(0, 0)
