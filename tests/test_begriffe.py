#!/usr/bin/env python3
"""Prueft die Begriffsliste (kern/begriffe.py) auf Form, nicht auf Inhalt.

    python -m tests.test_begriffe
"""
import sys

from smartsearch.kern import begriffe


def main():
    fehler = []
    for wort, liste in begriffe.BEGRIFFE.items():
        if wort != wort.lower() or any(b != b.lower() for b in liste):
            fehler.append(f"{wort}: nicht klein geschrieben")
        if wort in liste:
            fehler.append(f"{wort}: verweist auf sich selbst")
        if len(set(liste)) != len(liste):
            fehler.append(f"{wort}: doppelte Begriffe")
        if not liste:
            fehler.append(f"{wort}: leere Liste")

    if begriffe.anfrage_fuer_modell("Mietvertrag Berlin") != "Mietvertrag Berlin":
        fehler.append("Anfrage ohne Listenwort wurde veraendert")
    if begriffe.anfrage_fuer_modell("GEZ") != "GEZ (rundfunkbeitrag, beitragsservice)":
        fehler.append("GEZ wird nicht ergaenzt")
    if not begriffe.wort_oder_begriff_trifft("gez", "der rundfunkbeitrag ist faellig"):
        fehler.append("Begriff zaehlt nicht als Stichworttreffer")
    if begriffe.wort_oder_begriff_trifft("gez", "der mietvertrag"):
        fehler.append("Stichworttreffer ohne Wort und ohne Begriff")

    for f in fehler:
        print("FEHLER:", f)
    print(f"{len(begriffe.BEGRIFFE)} Eintraege, {len(fehler)} Fehler")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
