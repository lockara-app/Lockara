#!/usr/bin/env python3
"""
ocr_vergleich.py - Texterkennung messen: RapidOCR, Apple Vision, Tesseract.

    venv/bin/python -m werkzeuge.ocr_vergleich
        die neun Scans aus tests/testdokumente. Verglichen wird mit dem
        Text, aus dem die Scans erzeugt wurden (werkzeuge/testdokumente) -
        es gibt also eine echte Soll-Antwort.

    venv/bin/python -m werkzeuge.ocr_vergleich ~/Pfad/zu/Scans
        eigene, echte Scans (PDF). Hier gibt es keine Soll-Antwort; gezeigt
        wird, wie viele Woerter jede Erkennung liefert und wie gut sie
        uebereinstimmen. Die erkannten Texte landen zum Nachlesen in
        ocr-vergleich/ im Projektordner (nicht im Repository).

Gemessen wird jede Erkennung, die auf diesem Rechner verfuegbar ist:
Vision nur auf dem Mac, Tesseract nur mit installiertem tesseract-Programm.

Kennzahlen
----------
Woerter  Anteil der Woerter (ab 3 Buchstaben) aus dem Original, die im
         erkannten Text vorkommen. Das ist, was fuer die Suche zaehlt.
Zeichen  Aehnlichkeit Zeichen fuer Zeichen (0 bis 1), streng: auch
         Leerzeichen und Zeilenfolge zaehlen mit.
"""

import difflib
import os
import re
import sys
import time

from lockara.kern import ocr
from lockara.kern.pfade import PROJEKT_ORDNER


def _norm(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _woerter(text):
    return [w for w in re.findall(r"\w+", (text or "").lower()) if len(w) > 2]


def _bewerten(soll, ist):
    zeichen = difflib.SequenceMatcher(None, _norm(soll), _norm(ist), autojunk=False).ratio()
    erkannt = set(_woerter(ist))
    woerter = _woerter(soll)
    anteil = sum(1 for w in woerter if w in erkannt) / max(1, len(woerter))
    return zeichen, anteil


def _verfuegbare():
    wege = []
    if ocr._pruefe_pdfium() and ocr._pruefe_rapidocr():
        wege.append(("RapidOCR", ocr._ocr_mit_rapidocr))
    if ocr._pruefe_pdfium() and ocr._pruefe_vision():
        wege.append(("Vision", ocr._ocr_mit_vision))
    if ocr._pruefe_tesseract():
        wege.append(("Tesseract", ocr._ocr_mit_tesseract))
    return wege


def _soll_text(dok):
    zeilen = [z.lstrip("# ").strip() for z in dok.inhalt if z not in ("", "---")]
    if dok.stempel:
        zeilen += dok.stempel.split("|")
    return "\n".join(zeilen)


def testset():
    from werkzeuge.testdokumente import haushalt, kanzlei

    wege = _verfuegbare()
    print("Verfuegbar:", ", ".join(n for n, _ in wege) or "KEINE")
    scans = [d for d in haushalt.DOKUMENTE + kanzlei.DOKUMENTE if d.art == "scan"]
    summe = {n: [0.0, 0.0, 0.0] for n, _ in wege}
    for dok in scans:
        pfad = os.path.join(PROJEKT_ORDNER, "tests", "testdokumente", dok.datei)
        soll = _soll_text(dok)
        for name, lesen in wege:
            t0 = time.time()
            ist = lesen(pfad)
            dauer = time.time() - t0
            zeichen, woerter = _bewerten(soll, ist)
            s = summe[name]
            s[0] += zeichen
            s[1] += woerter
            s[2] += dauer
            print(f"  {os.path.basename(dok.datei):26} {name:10} Woerter {woerter:6.1%}  "
                  f"Zeichen {zeichen:.3f}  {dauer:5.1f} s", flush=True)
    print()
    print(f"ERGEBNIS ({len(scans)} Scans)")
    for name, (z, w, d) in summe.items():
        print(f"  {name:10} Woerter {w / len(scans):6.1%}  Zeichen {z / len(scans):.3f}  zusammen {d:5.1f} s")


def eigener_ordner(ordner):
    wege = _verfuegbare()
    print("Verfuegbar:", ", ".join(n for n, _ in wege) or "KEINE")
    ziel = os.path.join(PROJEKT_ORDNER, "ocr-vergleich")
    os.makedirs(ziel, exist_ok=True)
    pdfs = sorted(os.path.join(w, f) for w, _, dateien in os.walk(os.path.expanduser(ordner))
                  for f in dateien if f.lower().endswith(".pdf"))
    for pfad in pdfs:
        texte = {}
        for name, lesen in wege:
            t0 = time.time()
            texte[name] = lesen(pfad) or ""
            dauer = time.time() - t0
            with open(os.path.join(ziel, f"{os.path.basename(pfad)}.{name}.txt"), "w",
                      encoding="utf-8") as f:
                f.write(texte[name])
            print(f"  {os.path.basename(pfad)[:30]:30} {name:10} {len(_woerter(texte[name])):5d} Woerter  "
                  f"{dauer:5.1f} s", flush=True)
        namen = list(texte)
        for i, a in enumerate(namen):
            for b in namen[i + 1:]:
                wa, wb = set(_woerter(texte[a])), set(_woerter(texte[b]))
                gemeinsam = len(wa & wb) / max(1, len(wa | wb))
                print(f"      {a} / {b}: {gemeinsam:.0%} gemeinsame Woerter")
    print(f"\nDie erkannten Texte liegen in {ziel}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        eigener_ordner(sys.argv[1])
    else:
        testset()
