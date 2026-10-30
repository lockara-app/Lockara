#!/usr/bin/env python3
"""
personensuche_messen.py - misst die Personensuche an den 50 Testdokumenten.

    venv/bin/python -m werkzeuge.personensuche_messen
    venv/bin/python -m werkzeuge.personensuche_messen --ausfuehrlich

Baut einen frischen Index aus tests/personendokumente (eigener Datenordner,
der echte Index bleibt unberuehrt), sucht jede Testperson aus
werkzeuge/testdokumente/personen.py und vergleicht mit SOLL:

    FEHLT       eine Datei, in der die Person vorkommt, wurde nicht gefunden
    ZU VIEL     eine Datei wurde gefunden, in der die Person nicht vorkommt
    STUFE       gefunden, aber anders eingestuft als erwartet
    VERWECHSELT ein Namensvetter o. ae. steht als "sicher" da

Beim ersten Lauf werden die Scans per Texterkennung gelesen (etwa eine
Minute). Der Index bleibt im Ordner aus LOCKARA_DATENORDNER liegen; wer
denselben Ordner wieder angibt, spart das Einlesen.
"""

import os
import sys
import tempfile
import time

# Muss VOR dem ersten Import aus lockara stehen: pfade.py legt den
# Datenordner beim Import fest.
if not os.environ.get("LOCKARA_DATENORDNER"):
    os.environ["LOCKARA_DATENORDNER"] = tempfile.mkdtemp(prefix="lockara-personen-")

from lockara.kern import personensuche as ps  # noqa: E402
from lockara.kern.pfade import INDEX_FILE  # noqa: E402
from werkzeuge.testdokumente import personen as testfall  # noqa: E402

AUSFUEHRLICH = "--ausfuehrlich" in sys.argv


def _index_bauen():
    from lockara.kern import indexierung, ordner
    if not os.path.exists(testfall.ZIEL) or len(os.listdir(testfall.ZIEL)) == 0:
        sys.exit("Testdokumente fehlen. Erst: venv/bin/python -m werkzeuge.testdokumente.personen")
    # Fehlt nur ein Teil (z. B. weil .gitignore *.docx ausschloss), saehe die
    # Messung still schlechter aus. Deshalb hier laut abbrechen.
    fehlend = sorted(d for d in testfall.SOLL if not os.path.exists(os.path.join(testfall.ZIEL, d)))
    if fehlend:
        sys.exit(f"{len(fehlend)} von {len(testfall.SOLL)} Testdokumenten fehlen, die Messung waere falsch:\n    "
                 + "\n    ".join(fehlend)
                 + "\nNeu erzeugen: venv/bin/python -m werkzeuge.testdokumente.personen")
    ordner.befehl_ordner_hinzufuegen(testfall.ZIEL)
    if os.path.exists(INDEX_FILE):
        return 0.0
    start = time.time()
    indexierung.alles_indexieren([testfall.ZIEL], soll_abbrechen=lambda: False, melden=lambda e: None)
    return time.time() - start


def main():
    dauer = _index_bauen()
    if dauer:
        print(f"Index gebaut in {dauer:.0f} s ({os.environ['LOCKARA_DATENORDNER']})")

    gesamt_fehler = 0
    relevant_soll = relevant_gefunden = 0
    for kurz, angaben in testfall.PERSONEN.items():
        person = ps.Person(**angaben)
        start = time.time()
        ergebnis = ps.durchsuchen(person)
        zeit = time.time() - start

        ist = {os.path.relpath(f.datei, testfall.ZIEL): f for f in ergebnis.funde}
        soll = {d: s[kurz] for d, s in testfall.SOLL.items() if kurz in s}

        zeilen = []
        for datei, stufe in sorted(soll.items()):
            gemeint = (datei, kurz) not in testfall.NICHT_GEMEINT
            if gemeint:
                relevant_soll += 1
            if datei not in ist:
                zeilen.append(("FEHLT", datei, f"soll {stufe}"))
                continue
            if gemeint:
                relevant_gefunden += 1
            if ist[datei].stufe != stufe:
                zeilen.append(("STUFE", datei, f"ist {ist[datei].stufe}, soll {stufe}  "
                                               f"{ps.merkmale_zum_zeigen(ist[datei].merkmale)}"))
            if not gemeint and ist[datei].stufe == ps.SICHER:
                zeilen.append(("VERWECHSELT", datei, "andere Person als sicher eingestuft"))
        for datei, f in sorted(ist.items()):
            if datei not in soll:
                s = f.stellen[0]
                zeilen.append(("ZU VIEL", datei, f"{f.stufe} {ps.merkmale_zum_zeigen(f.merkmale)} "
                                                 f"»{s.treffer}« in …{s.vor[-25:]}"))

        gesamt_fehler += len(zeilen)
        print(f"\n{kurz}  {angaben['name']:28} {len(ist):2} gefunden, {len(soll):2} erwartet, "
              f"{len(zeilen)} Abweichungen, {zeit * 1000:.0f} ms")
        for art, datei, text in zeilen:
            print(f"    {art:11} {datei:55} {text}")
        if AUSFUEHRLICH:
            for datei, f in sorted(ist.items()):
                print(f"      {f.stufe:14} {datei:55} {ps.merkmale_zum_zeigen(f.merkmale)}")

    print(f"\nGefunden: {relevant_gefunden} von {relevant_soll} Dateien, in denen die Person "
          f"wirklich vorkommt. Abweichungen insgesamt: {gesamt_fehler}")
    return 1 if gesamt_fehler else 0


if __name__ == "__main__":
    sys.exit(main())
