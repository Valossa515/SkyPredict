def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_previsao_sem_parametros_retorna_400(client):
    resp = client.get("/previsao")
    assert resp.status_code == 400
    assert "erro" in resp.get_json()


def test_previsao_lat_fora_dos_limites_retorna_400(client):
    resp = client.get("/previsao?lat=999&lon=0&data=2024-01-01")
    assert resp.status_code == 400


def test_previsao_data_invalida_retorna_400(client):
    resp = client.get("/previsao?lat=0&lon=0&data=xx")
    assert resp.status_code == 400


def test_exportar_sem_parametros_retorna_400(client):
    resp = client.get("/exportar_excel")
    assert resp.status_code == 400


def test_mapa_formato_json(client, monkeypatch):
    import routes.mapa as mapa

    def fake_sugestao(origem_id, destino_id, data_futura):
        return {
            "origem": "GRU",
            "destino": "JFK",
            "data": data_futura,
            "risco_origem": "Baixo",
            "risco_destino": "Alto",
            "rotas": {"routes": []},
            "sugestao": "Evitar voo devido a alto risco meteorológico.",
        }

    coords = {"GRU": (-23.4356, -46.4731), "JFK": (40.6413, -73.7781)}

    monkeypatch.setattr(mapa, "gerar_sugestao_rota", fake_sugestao)
    monkeypatch.setattr(mapa, "obter_coordenadas_aeroporto", lambda i: coords[i])

    resp = client.get("/mapa_sugerido?origem_id=GRU&destino_id=JFK&data=2024-10-15&formato=json&corredor_km=500&limite=8")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["origem"] == "GRU"
    assert data["distancia_direta_km"] > 7000
    assert "aeroportos_no_caminho" in data
    assert "rotas_alternativas" in data
    aeroportos = data["aeroportos_no_caminho"]
    assert aeroportos  # encontrou hubs no caminho
    assert len(aeroportos) <= 8  # respeita o limite
    # cada rota alternativa é uma escala origem -> hub -> destino
    for alt in data["rotas_alternativas"]:
        assert alt["escalas"][0] == "GRU" and alt["escalas"][-1] == "JFK"


def test_mapa_html(client, monkeypatch):
    import routes.mapa as mapa

    monkeypatch.setattr(mapa, "gerar_sugestao_rota", lambda o, d, dt: {
        "origem": "GRU", "destino": "JFK", "data": dt,
        "risco_origem": "Baixo", "risco_destino": "Baixo",
        "rotas": {"routes": []}, "sugestao": "Rota segura.",
    })
    coords = {"GRU": (-23.4356, -46.4731), "JFK": (40.6413, -73.7781)}
    monkeypatch.setattr(mapa, "obter_coordenadas_aeroporto", lambda i: coords[i])

    resp = client.get("/mapa_sugerido?origem_id=GRU&destino_id=JFK&data=2024-10-15")
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"
