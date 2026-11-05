"""CBS StatLine 85592NED: gemiddelde energietarieven voor consumenten (maandelijks).

Haalt de open OData-API op en zet gas- en stroomtarieven om naar platte rijen per maand,
incl. en excl. btw. Geen API-sleutel nodig. Bron: https://opendata.cbs.nl/ODataApi/OData/85592NED
"""
from __future__ import annotations

import re

import requests

BASE = "https://opendata.cbs.nl/ODataApi/OData/85592NED"
TIMEOUT = 60

# Veldnamen zoals CBS ze publiceert (DataProperties, gecontroleerd nov 2026)
GAS = {
    "Transporttarief_1": "transport",                       # €/jaar, netbeheer
    "VastLeveringstariefVasteEnVar_2": "vastrecht",         # €/jaar
    "VariabelLeveringstariefContractprijs_3": "levering",   # €/m³
    "OpslagDuurzameEnergieODE_5": "ode",                    # €/m³ (t/m 2022)
    "Energiebelasting_6": "energiebelasting",               # €/m³
}
STROOM = {
    "Transporttarief_7": "transport",
    "VastLeveringstariefVasteEnVar_8": "vastrecht",
    "VariabelLeveringstariefContractprijs_9": "levering",
    "VastLeveringstariefDynamisch_11": "vastrecht_dynamisch",
    "VariabelLeveringstariefDynamisch_12": "levering_dynamisch",
    "OpslagDuurzameEnergieODE_13": "ode",
    "Energiebelasting_14": "energiebelasting",
    "VerminderingEnergiebelasting_15": "vermindering_eb",
}


def _get(path: str, params: dict | None = None) -> list[dict]:
    """Haalt alle rijen op, inclusief vervolgpagina's (odata.nextLink)."""
    url, rows = f"{BASE}/{path}", []
    while url:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        body = r.json()
        rows += body.get("value", [])
        url, params = body.get("odata.nextLink"), None
    return rows


def check_schema() -> None:
    """Stopt met een duidelijke fout als CBS veldnamen heeft gewijzigd."""
    keys = {p.get("Key") for p in _get("DataProperties")}
    missing = [k for k in (*GAS, *STROOM) if k not in keys]
    if missing:
        raise RuntimeError(f"CBS 85592NED: velden niet gevonden: {missing}. Controleer DataProperties.")


def btw_codes() -> dict[str, str]:
    """Zoekt de codes voor 'inclusief' en 'exclusief' btw op (bijv. A048944 / A048945)."""
    codes = {}
    for c in _get("Btw"):
        title = c.get("Title", "").lower()
        if "inclusief" in title:
            codes["incl"] = c["Key"].strip()
        elif "exclusief" in title:
            codes["excl"] = c["Key"].strip()
    if set(codes) != {"incl", "excl"}:
        raise RuntimeError(f"CBS 85592NED: btw-codes niet herkend: {codes}")
    return codes


def periode_naar_maand(p: str) -> str | None:
    """'2026MM09' -> '2026-09'; jaar- en kwartaalcijfers worden overgeslagen."""
    m = re.fullmatch(r"(\d{4})MM(\d{2})", p.strip())
    return f"{m.group(1)}-{m.group(2)}" if m else None


def transform(rows: list[dict], codes: dict[str, str], velden: dict[str, str]) -> list[dict]:
    """Zet TypedDataSet-rijen om naar één rij per maand met *_incl en *_excl kolommen."""
    per_maand: dict[str, dict] = {}
    rev = {v: k for k, v in codes.items()}
    for r in rows:
        maand = periode_naar_maand(r.get("Perioden", ""))
        soort = rev.get(str(r.get("Btw", "")).strip())
        if not maand or not soort:
            continue
        uit = per_maand.setdefault(maand, {"maand": maand})
        for key, naam in velden.items():
            v = r.get(key)
            uit[f"{naam}_{soort}"] = 0.0 if v is None and naam == "ode" else v
    out = [r for _, r in sorted(per_maand.items()) if r.get("levering_incl") is not None]
    return out


def fetch(vanaf: str = "2022-01") -> dict:
    check_schema()
    codes = btw_codes()
    rows = _get("TypedDataSet")
    gas = [r for r in transform(rows, codes, GAS) if r["maand"] >= vanaf]
    stroom = [r for r in transform(rows, codes, STROOM) if r["maand"] >= vanaf]
    if not gas:
        raise RuntimeError("CBS 85592NED: geen maandcijfers voor gas ontvangen")
    return {"gas": gas, "stroom": stroom}
