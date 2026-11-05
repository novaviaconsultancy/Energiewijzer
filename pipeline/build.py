"""Bouwt public/data/energie.json: één bestand met alle data voor de Energiewijzer.

Automatisch:  CBS (maandelijks, open API) en TTF (dagelijks).
Handmatig:    bestanden in data/manual/ (ACM-mediaan, leveranciers, nieuws, termijnaannames,
              belastingstatus). Die werk je bij met een commit; het script neemt ze mee.

Faalt een bron, dan blijft de vorige versie van die bron staan en komt er een melding in
het wijzigingslog. De pagina toont zo nooit een lege grafiek.

Gebruik:  python -m pipeline.build            (alles ophalen)
          python -m pipeline.build --offline  (alleen handmatige bestanden; voor testen)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "data" / "manual"
OUT = ROOT / "public" / "data" / "energie.json"
LOG_MAX = 200


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def lees(pad: Path, standaard=None):
    return json.loads(pad.read_text(encoding="utf-8")) if pad.exists() else standaard


def bron(naam, url, rijen, laatste, schema, status="ok", melding=None):
    return {"naam": naam, "url": url, "rijen": rijen, "laatste_periode": laatste,
            "bijgewerkt": now(), "schema": schema, "status": status, "melding": melding}


def main(offline: bool = False) -> int:
    vorig = lees(OUT, {}) or {}
    data = {k: vorig.get(k) for k in ("cbs_gas", "cbs_stroom", "ttf_dag")}
    bronnen = dict(vorig.get("bronnen", {}))
    log = list(vorig.get("wijzigingslog", []))

    def logboek(bron_id, tekst):
        log.insert(0, {"tijd": now(), "bron": bron_id, "tekst": tekst})

    # --- CBS (automatisch) ---
    if not offline:
        try:
            from pipeline import fetch_cbs
            cbs = fetch_cbs.fetch()
            oud = (data.get("cbs_gas") or [{}])[-1].get("maand")
            data["cbs_gas"], data["cbs_stroom"] = cbs["gas"], cbs["stroom"]
            nieuw = cbs["gas"][-1]["maand"]
            bronnen["cbs"] = bron("CBS StatLine 85592NED", fetch_cbs.BASE, len(cbs["gas"]), nieuw, "maandelijks, rond de 2e donderdag")
            if nieuw != oud:
                logboek("cbs", f"Nieuwe CBS-maand: {nieuw} (was {oud})")
        except Exception as e:  # vorige versie blijft staan
            if "cbs" in bronnen:
                bronnen["cbs"].update(status="fout", melding=str(e)[:300])
            logboek("cbs", f"Ophalen mislukt, vorige versie behouden: {e}")

    # --- TTF dagkoers (automatisch) ---
    if not offline:
        try:
            from pipeline import fetch_ttf
            dag = fetch_ttf.fetch_daily()
            oud = (data.get("ttf_dag") or [{}])[-1].get("datum")
            data["ttf_dag"] = dag
            bronnen["ttf_dag"] = bron("TTF front-month slotkoers (Yahoo Finance TTF=F)", "https://finance.yahoo.com/quote/TTF%3DF",
                                      len(dag), dag[-1]["datum"], "dagelijks op werkdagen")
            if dag[-1]["datum"] != oud:
                logboek("ttf_dag", f"TTF {dag[-1]['datum']}: €{dag[-1]['slot']:.2f}/MWh")
        except Exception as e:
            if "ttf_dag" in bronnen:
                bronnen["ttf_dag"].update(status="fout", melding=str(e)[:300])
            logboek("ttf_dag", f"Ophalen mislukt, vorige versie behouden: {e}")

    # --- TTF maandindex: handmatige EEX-index, aangevuld met dag-gemiddelden ---
    maand = lees(MANUAL / "ttf_maandindex.json", [])
    bekend = {r["maand"] for r in maand}
    if data.get("ttf_dag"):
        from pipeline.fetch_ttf import maandgemiddelden
        for m, v in maandgemiddelden(data["ttf_dag"]).items():
            if m not in bekend:
                maand.append({"maand": m, "ttf": v, "bron": "gemiddelde dagkoers"})
    maand.sort(key=lambda r: r["maand"])
    data["ttf_maand"] = maand

    # --- Handmatige bronnen ---
    handmatig = {
        "ttf_termijn": ("ttf_termijn.json", "TTF-termijnaannames", "bij grote marktbewegingen"),
        "acm_mediaan": ("acm_mediaan_gas.json", "ACM Monitor Consumentenmarkt Energie", "maandelijks, rond het midden van de maand"),
        "leveranciers": ("leveranciers_gas.json", "Tarieven per leverancier", "wekelijks"),
        "nieuws": ("nieuws.json", "Nieuws gasmarkt", "wekelijks"),
        "belasting": ("belasting.json", "Energiebelasting en status Belastingplan", "jaarlijks, na stemming Eerste Kamer"),
    }
    for key, (bestand, naam, schema) in handmatig.items():
        pad = MANUAL / bestand
        inhoud = lees(pad)
        if inhoud is None:
            continue
        gewijzigd = datetime.fromtimestamp(pad.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        if json.dumps(inhoud, sort_keys=True) != json.dumps(vorig.get(key), sort_keys=True) and key in vorig:
            logboek(key, f"{naam} handmatig bijgewerkt")
        data[key] = inhoud
        rijen = len(inhoud) if isinstance(inhoud, list) else 1
        bronnen[key] = {**bron(naam, f"data/manual/{bestand}", rijen, None, schema), "bijgewerkt": gewijzigd}

    uit = {"versie": 1, "gegenereerd": now(), "bronnen": bronnen, **data, "wijzigingslog": log[:LOG_MAX]}
    if not uit.get("cbs_gas"):
        print("Geen CBS-data beschikbaar; bestand niet geschreven.", file=sys.stderr)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(uit, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Geschreven: {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} kB)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    sys.exit(main(ap.parse_args().offline))
