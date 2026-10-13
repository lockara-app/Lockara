#!/usr/bin/env python3
"""
ci_pruefen.py - Suchqualitaet messen und mit den Untergrenzen vergleichen.

Laeuft bei jedem Pull Request auf GitHub (.github/workflows/tests.yml),
laesst sich aber genauso lokal aufrufen:

    venv/bin/python -m werkzeuge.ci_pruefen

Startet die Suchdiagnose mit den 50 Testdokumenten, liest das Ergebnis
("ERGEBNIS: 48 von 67 Anfragen richtig · 115 Fehlgriffe") und vergleicht
es mit tests/mindestwerte.json. Faellt die Suche darunter, endet das
Programm mit Fehlercode 1 - auf GitHub wird der Pull Request rot.

Gemessen wird der ANTEIL richtiger Anfragen, nicht die Zahl: die Zahl der
Testfaelle aendert sich von Zeit zu Zeit (tests/suchfaelle.py).
"""

import json
import os
import re
import subprocess
import sys

from smartsearch.kern.pfade import PROJEKT_ORDNER

MINDESTWERTE = os.path.join(PROJEKT_ORDNER, "tests", "mindestwerte.json")
MUSTER = re.compile(r"ERGEBNIS: (\d+) von (\d+) Anfragen richtig\s+\S\s+(\d+) Fehlgriffe")


def auswerten(ausgabe, grenzen):
    treffer = MUSTER.search(ausgabe)
    if not treffer:
        return False, "Kein ERGEBNIS in der Ausgabe der Suchdiagnose gefunden."
    richtig, gesamt, fehlgriffe = (int(x) for x in treffer.groups())
    anteil = richtig / gesamt
    zeilen = [
        f"Richtig:     {richtig} von {gesamt} ({anteil:.1%}), Untergrenze {grenzen['anteil_richtig_min']:.1%}",
        f"Fehlgriffe:  {fehlgriffe}, Obergrenze {grenzen['fehlgriffe_max']}",
    ]
    ok = anteil >= grenzen["anteil_richtig_min"] and fehlgriffe <= grenzen["fehlgriffe_max"]
    zeilen.append("BESTANDEN" if ok else "NICHT BESTANDEN - die Suche ist schlechter geworden")
    return ok, "\n".join(zeilen)


def main():
    with open(MINDESTWERTE, encoding="utf-8") as f:
        grenzen = json.load(f)
    lauf = subprocess.run(
        [sys.executable, "-u", "-m", "werkzeuge.such_diagnose", "--testdokumente"],
        cwd=PROJEKT_ORDNER, capture_output=True, text=True)
    ausgabe = lauf.stdout + lauf.stderr
    # Die vollstaendige Diagnose gehoert ins Protokoll - bei einem roten
    # Lauf will man sehen, welche Anfragen gekippt sind.
    print(ausgabe)
    ok, bericht = auswerten(ausgabe, grenzen)
    print("=" * 78)
    print(bericht)
    zusammenfassung = os.environ.get("GITHUB_STEP_SUMMARY")
    if zusammenfassung:
        with open(zusammenfassung, "a", encoding="utf-8") as f:
            f.write("### Suchqualitaet\n\n```\n" + bericht + "\n```\n")
    return 0 if ok and lauf.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
