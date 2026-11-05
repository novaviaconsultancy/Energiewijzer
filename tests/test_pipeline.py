"""Tests zonder netwerk: controleren de omzetting van CBS-rijen en de TTF-hulpfuncties."""
import json
from pathlib import Path

from pipeline.fetch_cbs import GAS, periode_naar_maand, transform
from pipeline.fetch_ttf import maandgemiddelden

SNAP = json.loads((Path(__file__).parent / "cbs_gas_snapshot.json").read_text())


def _als_cbs_rijen(snapshot):
    """Bouwt nep-TypedDataSet-rijen uit een eerdere momentopname."""
    rev = {v: k for k, v in GAS.items()}
    rijen = []
    for r in snapshot:
        jaar, mnd = r["maand"].split("-")
        for code, soort in (("A048944", "incl"), ("A048945", "excl")):
            rij = {"Btw": code + " ", "Perioden": f"{jaar}MM{mnd}"}
            for naam, key in rev.items():
                bron = {"transport": "transport", "vastrecht": "vastrecht", "levering": "levering",
                        "ode": "ode", "energiebelasting": "energiebelasting"}[naam]
                rij[key] = r[f"{bron}_{soort}"]
            rijen.append(rij)
    rijen.append({"Btw": "A048944", "Perioden": "2026JJ00", "Transporttarief_1": 1})  # jaarcijfer: overslaan
    return rijen


def test_periode():
    assert periode_naar_maand("2026MM09") == "2026-09"
    assert periode_naar_maand("2026JJ00") is None
    assert periode_naar_maand("2026KW03") is None


def test_transform_gas():
    rijen = _als_cbs_rijen(SNAP)
    uit = transform(rijen, {"incl": "A048944", "excl": "A048945"}, GAS)
    assert len(uit) == len(SNAP)
    laatste = uit[-1]
    assert laatste["maand"] == SNAP[-1]["maand"]
    assert abs(laatste["levering_incl"] - SNAP[-1]["levering_incl"]) < 1e-9
    assert abs(laatste["energiebelasting_excl"] - SNAP[-1]["energiebelasting_excl"]) < 1e-9
    assert all(r["maand"] < s["maand"] for r, s in zip(uit, uit[1:]))


def test_maandgemiddelden():
    dag = [{"datum": "2026-11-02", "slot": 94.0}, {"datum": "2026-11-03", "slot": 92.0}, {"datum": "2026-10-31", "slot": 100.0}]
    assert maandgemiddelden(dag) == {"2026-10": 100.0, "2026-11": 93.0}
