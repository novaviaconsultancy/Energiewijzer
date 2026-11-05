# Nova Via Energiewijzer – data

Haalt elke ochtend de energiedata op en schrijft één bestand, `public/data/energie.json`,
dat de Energiewijzer-pagina op nova-via.nl inleest.

## Wat gebeurt automatisch, wat doe je zelf?

| Bron | Hoe | Wanneer |
|---|---|---|
| CBS 85592NED (gas + stroom, incl./excl. btw) | automatisch, open API | elke ochtend gecontroleerd; CBS publiceert maandelijks |
| TTF-dagkoers (front-month) | automatisch, Yahoo Finance `TTF=F` | elke werkdag |
| TTF-maandindex (EEX) | `data/manual/ttf_maandindex.json`; ontbrekende maanden vult het script aan met de gemiddelde dagkoers | maandelijks |
| TTF-termijnaannames | `data/manual/ttf_termijn.json` | bij grote marktbewegingen |
| ACM-mediaan nieuwe contracten | `data/manual/acm_mediaan_gas.json` | maandelijks (Claude leest de SVG-download uit) |
| Tarieven per leverancier | `data/manual/leveranciers_gas.json` | wekelijks |
| Nieuws | `data/manual/nieuws.json` | wekelijks |
| Energiebelasting + status | `data/manual/belasting.json` | na de stemming in de Eerste Kamer |

Faalt een automatische bron, dan blijft de vorige versie staan en staat de fout in
`bronnen.<bron>.melding` en in het `wijzigingslog`. De pagina blijft dus altijd werken.

## Eenmalig instellen (±15 minuten)

1. Maak op github.com een nieuwe repository, bijvoorbeeld `energiewijzer`.
2. Upload de inhoud van deze map (sleep alle bestanden en mappen in de webinterface, inclusief de map `.github`).
3. Ga naar **Settings → Actions → General → Workflow permissions** en kies **Read and write permissions**.
4. Ga naar het tabblad **Actions**, kies **Energiedata bijwerken** en klik **Run workflow**.
   Na ±1 minuut staat er een verse `public/data/energie.json`.
5. Publiceer de data: **Settings → Pages → Deploy from a branch**, branch `main`, map `/ (root)`.
   De data staat dan op `https://<gebruikersnaam>.github.io/energiewijzer/public/data/energie.json`.

## Handmatig bijwerken

Pas een bestand in `data/manual/` aan (op github.com: potloodje → wijzigen → commit).
De workflow start dan vanzelf en zet de wijziging binnen een minuut in `energie.json`.

## Lokaal testen

```bash
pip install -r requirements.txt
python -m pytest -q
python -m pipeline.build            # alles ophalen
python -m pipeline.build --offline  # alleen handmatige bestanden
```

## Let op

- **Openbaar of privé:** `leveranciers_gas.json` bevat tarieven uit het overzicht van Energievergelijk.nl.
  Houd de repository privé of haal dat bestand weg tot je toestemming hebt. GitHub Pages vanuit een
  privé-repository vereist een betaald GitHub-abonnement.
- **TTF-dagkoers:** Yahoo Finance is een gratis, onofficiële bron. Voor een officiële feed vervang je
  `fetch_daily()` in `pipeline/fetch_ttf.py` door een betaalde API met dezelfde uitvoer.
- **CBS-velden:** controleert bij elke run of de veldnamen nog bestaan en stopt met een duidelijke fout als CBS de tabel wijzigt.
