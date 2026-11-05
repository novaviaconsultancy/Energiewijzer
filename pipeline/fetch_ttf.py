"""Dagelijkse TTF-slotkoers (front-month future, €/MWh).

Standaardbron: Yahoo Finance-ticker 'TTF=F' (ICE Endex Dutch TTF front month) via het
yfinance-pakket. Dat is een gratis, onofficiële route: prima voor een indicatief
consumentendashboard, maar zonder garanties. Wil je een officiële feed, vervang dan
fetch_daily() door een betaalde API (bijv. ICE, EEX of een datavendor) met dezelfde uitvoer.
"""
from __future__ import annotations

from datetime import date, timedelta


def fetch_daily(dagen: int = 400) -> list[dict]:
    import yfinance as yf  # alleen nodig in de pipeline

    start = date.today() - timedelta(days=dagen)
    hist = yf.Ticker("TTF=F").history(start=start.isoformat(), interval="1d", auto_adjust=False)
    if hist is None or hist.empty:
        raise RuntimeError("TTF: geen koersen ontvangen van Yahoo Finance")
    rows = []
    for ts, rij in hist.iterrows():
        slot = float(rij["Close"])
        if slot > 0:
            rows.append({"datum": ts.date().isoformat(), "slot": round(slot, 3)})
    return rows


def maandgemiddelden(dag: list[dict]) -> dict[str, float]:
    """Gemiddelde slotkoers per kalendermaand, als aanvulling op de EEX-maandindex."""
    som: dict[str, list[float]] = {}
    for r in dag:
        som.setdefault(r["datum"][:7], []).append(r["slot"])
    return {m: round(sum(v) / len(v), 3) for m, v in sorted(som.items())}
