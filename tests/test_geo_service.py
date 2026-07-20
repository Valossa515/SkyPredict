from services.geo_service import (
    distancia_km,
    pontos_geodesicos,
    aeroportos_no_corredor,
    carregar_aeroportos,
)

GRU = (-23.4356, -46.4731)
JFK = (40.6413, -73.7781)
CGH = (-23.6266, -46.6564)


def test_distancia_km_conhecida():
    # GRU -> JFK ~ 7600 km
    d = distancia_km(*GRU, *JFK)
    assert 7000 < d < 8200


def test_distancia_mesmo_ponto_zero():
    assert distancia_km(*GRU, *GRU) == 0.0


def test_pontos_geodesicos_inclui_extremos():
    pts = pontos_geodesicos(*GRU, *JFK, n=10)
    assert len(pts) == 11
    # primeiro ponto na origem, último no destino (tolerância a arredondamento)
    assert abs(pts[0][0] - GRU[0]) < 1e-3 and abs(pts[0][1] - GRU[1]) < 1e-3
    assert abs(pts[-1][0] - JFK[0]) < 0.5
    assert abs(pts[-1][1] - JFK[1]) < 0.5


def test_aeroportos_no_corredor_encontra_intermediarios():
    inter = aeroportos_no_corredor(*GRU, *JFK, corredor_km=500, excluir_iatas=["GRU", "JFK"])
    assert inter  # deve encontrar aeroportos no caminho
    # ordenado por menor desvio
    desvios = [a["desvio_rota_km"] for a in inter]
    assert desvios == sorted(desvios)
    # todos dentro do corredor
    assert all(a["distancia_da_rota_km"] <= 500 for a in inter)
    # Brasília (Intl) está no caminho GRU -> JFK (lista completa, sem limite)
    assert "BSB" in {a["iata"] for a in inter}


def test_default_somente_internacionais():
    inter = aeroportos_no_corredor(*GRU, *JFK, corredor_km=500, excluir_iatas=["GRU", "JFK"])
    assert all(
        ("international" in a["nome"].lower()) or ("intl" in a["nome"].lower())
        for a in inter
    )


def test_incluir_todos_amplia_resultados():
    intl = aeroportos_no_corredor(*GRU, *JFK, corredor_km=400, excluir_iatas=["GRU", "JFK"])
    todos = aeroportos_no_corredor(
        *GRU, *JFK, corredor_km=400, excluir_iatas=["GRU", "JFK"], somente_internacionais=False
    )
    assert len(todos) >= len(intl)


def test_limite_corta_resultados():
    top5 = aeroportos_no_corredor(*GRU, *JFK, corredor_km=500, excluir_iatas=["GRU", "JFK"], limite=5)
    assert len(top5) <= 5


def test_aeroportos_no_corredor_respeita_exclusao():
    inter = aeroportos_no_corredor(*GRU, *JFK, corredor_km=500, excluir_iatas=["GRU", "JFK", "BSB"])
    assert "BSB" not in {a["iata"] for a in inter}


def test_corredor_estreito_reduz_resultados():
    largo = aeroportos_no_corredor(*GRU, *JFK, corredor_km=500, excluir_iatas=["GRU", "JFK"])
    estreito = aeroportos_no_corredor(*GRU, *JFK, corredor_km=50, excluir_iatas=["GRU", "JFK"])
    assert len(estreito) <= len(largo)


def test_base_aeroportos_valida():
    aps = carregar_aeroportos()
    assert len(aps) > 1000  # base completa da OurAirports (~7,9 mil com IATA)
    for a in aps:
        assert -90 <= a["lat"] <= 90
        assert -180 <= a["lon"] <= 180
        assert a["iata"]
