"""Gera ``data/airports.json`` a partir do pacote OurAirports (via `airportsdata`).

A base derivada da OurAirports é empacotada offline no pacote PyPI
``airportsdata``. Este script é executado apenas em tempo de build/manutenção —
a aplicação em runtime lê somente o JSON resultante, sem dependência extra.

Uso:
    pip install airportsdata
    python scripts/build_airports.py

Filtra para aeroportos com código IATA de 3 letras e coordenadas válidas.
"""
import json
import os
import re

import airportsdata

_IATA_RE = re.compile(r"^[A-Z]{3}$")
_OUT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "airports.json")


def build():
    fonte = airportsdata.load("IATA")  # dict chaveado por código IATA

    aeroportos = []
    for iata, info in fonte.items():
        if not _IATA_RE.match(iata):
            continue
        lat = info.get("lat")
        lon = info.get("lon")
        if lat is None or lon is None:
            continue
        # Descarta coordenadas obviamente inválidas (0,0 no golfo da Guiné).
        if lat == 0 and lon == 0:
            continue

        aeroportos.append({
            "iata": iata,
            "icao": info.get("icao") or "",
            "nome": info.get("name") or iata,
            "cidade": info.get("city") or "",
            "pais": info.get("country") or "",
            "lat": round(float(lat), 5),
            "lon": round(float(lon), 5),
        })

    aeroportos.sort(key=lambda a: a["iata"])

    with open(_OUT_PATH, "w", encoding="utf-8") as fh:
        # Uma linha por aeroporto: diff amigável e arquivo compacto.
        fh.write("[\n")
        for i, apt in enumerate(aeroportos):
            virgula = "," if i < len(aeroportos) - 1 else ""
            fh.write("  " + json.dumps(apt, ensure_ascii=False) + virgula + "\n")
        fh.write("]\n")

    print(f"Gerados {len(aeroportos)} aeroportos em {_OUT_PATH}")


if __name__ == "__main__":
    build()
