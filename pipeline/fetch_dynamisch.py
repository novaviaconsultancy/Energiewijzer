"""Dynamische gascontracten per leverancier, dagelijks.

Twee bronnen:
1. Gasmarktprijs per dag (EUR/m³, excl. btw) via de openbare EnergyZero-API (pakket `energyzero`).
   Dynamische leveranciers rekenen met deze dagprijs; een nieuwe prijs geldt vanaf 06:00.
2. Opslag en vaste kosten per leverancier uit de open dataset "energieprijzen-nl"
   (https://github.com/zhinees/energieprijzen-nl, data onder CC BY 4.0). Elk getal daarin is
   gelezen op de site of rekentool van de leverancier zelf en heeft een controledatum.
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from statistics import mean

import requests

ENERGIEPRIJZEN_URL = "https://raw.githubusercontent.com/zhinees/energieprijzen-nl/main/data/leveranciers.json"
ENERGIEPRIJZEN_REPO = "https://github.com/zhinees/energieprijzen-nl"


def _bedrag(v) -> float | None:
    if isinstance(v, dict):
        b = v.get("bedragInclBtw")
        return float(b) if isinstance(b, (int, float)) else None
    return float(v) if isinstance(v, (int, float)) else None


def leveranciers_uit(data: dict) -> list[dict]:
    """Haalt per leverancier de gasopslag en vaste gaskosten (incl. btw) uit energieprijzen-nl."""
    uit = []
    for l in data.get("leveranciers", []):
        t = l.get("tarieven", {}) or {}
        opslag, vast = _bedrag(t.get("gasInkoopopslag")), _bedrag(t.get("gasVastPerMaand"))
        if opslag is None or vast is None:
            continue  # leverancier zonder (gecontroleerd) gastarief
        gecontroleerd = [v.get("laatstGecontroleerd") or v.get("sinds") for v in (t.get("gasInkoopopslag"), t.get("gasVastPerMaand")) if isinstance(v, dict)]
        gecontroleerd = [g for g in gecontroleerd if g]
        uit.append({
            "naam": l.get("naam"),
            "opslag_incl": round(opslag, 5),           # EUR/m³ bovenop de marktprijs, incl. btw
            "vast_per_maand_incl": round(vast, 4),      # EUR/maand
            "gecontroleerd": max(gecontroleerd) if gecontroleerd else data.get("gegenereerdOp"),
            "website": l.get("website") or l.get("url"),
        })
    return sorted(uit, key=lambda x: x["naam"] or "")


def fetch_leveranciers() -> dict:
    r = requests.get(ENERGIEPRIJZEN_URL, timeout=60)
    r.raise_for_status()
    data = r.json()
    lev = leveranciers_uit(data)
    if len(lev) < 5:
        raise RuntimeError(f"energieprijzen-nl: maar {len(lev)} leveranciers met gastarief gevonden")
    return {"leveranciers": lev, "gegenereerd_bron": data.get("gegenereerdOp")}


async def _gas_dagen(dagen: int) -> list[dict]:
    from energyzero import EnergyZero, PriceType

    uit = []
    vandaag = date.today()
    async with EnergyZero() as client:
        for i in range(dagen - 1, -1, -1):
            d = vandaag - timedelta(days=i)
            try:
                p = await client.get_gas_prices(start_date=d, end_date=d, price_type=PriceType.MARKET)
            except Exception:  # dag zonder data (bijv. API-storing): overslaan
                continue
            prijs = p.average_price if p.average_price is not None else (mean(p.prices.values()) if p.prices else None)
            if prijs is not None and prijs > 0:
                uit.append({"datum": d.isoformat(), "markt_excl": round(float(prijs), 5)})
    return uit


def fetch_gasmarkt(dagen: int = 60) -> list[dict]:
    rows = asyncio.run(_gas_dagen(dagen))
    if not rows:
        raise RuntimeError("EnergyZero: geen gasprijzen ontvangen")
    return rows


def prijs_vandaag(markt_excl: float, eb_incl: float, opslag_incl: float, btw: float = 0.21) -> float:
    """All-in gasprijs per m³ voor een dynamisch contract: markt + btw + energiebelasting + opslag leverancier."""
    return round(markt_excl * (1 + btw) + eb_incl + opslag_incl, 4)
