#!/usr/bin/env python3
"""Prueft, dass Lockara mit kaputten Dateien, verschwundenen Dokumenten und
abgebrochenen Laeufen zurechtkommt - ohne Modell, in einer Sekunde.

    python -m tests.test_robustheit

Arbeitet in einem eigenen, leeren Datenordner (LOCKARA_DATENORDNER); der
echte Index und die echten Einstellungen werden nicht angefasst.
"""
import os
import shutil
import sys
import tempfile
import threading
import time

# MUSS vor dem ersten Import aus lockara stehen: pfade.py legt den
# Datenordner beim Import fest.
_ARBEIT = tempfile.mkdtemp(prefix="lockara-test-")
os.environ["LOCKARA_DATENORDNER"] = os.path.join(_ARBEIT, "daten")

import numpy as np  # noqa: E402

from lockara.kern import einstellungen, index, indexierung, ueberwachung  # noqa: E402
from lockara.kern.pfade import CONFIG_FILE  # noqa: E402

FEHLER = []


def pruefe(bedingung, text):
    print(f"  {'ok  ' if bedingung else 'FEHL'} {text}")
    if not bedingung:
        FEHLER.append(text)


class Probemodell:
    """Steht fuer das Suchmodell: liefert je Text einen festen Vektor."""

    def __init__(self, abbrechen_nach=None, abbruch=None):
        self.aufrufe = 0
        self.abbrechen_nach = abbrechen_nach
        self.abbruch = abbruch

    def encode(self, texte, **_):
        self.aufrufe += 1
        if self.abbrechen_nach and self.aufrufe >= self.abbrechen_nach:
            self.abbruch["jetzt"] = True
        return np.ones((len(texte), 4), dtype="float32") / 2


def einstellungen_pruefen():
    print("Einstellungen:")
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write('{"ordner": ["/a"')          # mitten im Schreiben abgebrochen
    config = einstellungen.lade_config()
    pruefe(config == {"ordner": []}, "kaputte config.json -> leere Einstellungen statt Absturz")
    pruefe(os.path.exists(CONFIG_FILE + ".defekt"), "kaputte Datei als .defekt aufgehoben")

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write('{"sprache": "de"}')
    pruefe(einstellungen.lade_config()["ordner"] == [], "fehlender Eintrag 'ordner' wird ergaenzt")

    einstellungen.speichere_config({"ordner": ["/Users/x/Bücher"]})
    pruefe(einstellungen.lade_config()["ordner"] == ["/Users/x/Bücher"], "Umlaute ueberstehen Speichern und Laden")
    pruefe(not os.path.exists(CONFIG_FILE + ".tmp"), "keine Hilfsdatei bleibt liegen")

    with open(einstellungen.VERLAUF_FILE, "w", encoding="utf-8") as f:
        f.write('{"kein": "verlauf"}')
    pruefe(einstellungen.lade_verlauf() == [], "Verlauf in falscher Form -> leerer Verlauf")


def zwischenstand_pruefen():
    print("Zwischenstand beim Indexieren:")
    neu = [
        {"datei": "/o/a.txt", "vektor": 1},
        {"datei": "/o/a.txt", "vektor": 2},
        {"datei": "/o/b.txt", "vektor": 1},
        {"datei": "/o/b.txt"},                  # zweiter Abschnitt noch ohne Vektor
        {"datei": "/o/c.pdf", "ohne_inhalt": True},
    ]
    alt = {"/o/b.txt": [{"datei": "/o/b.txt", "alt": True}],
           "/o/a.txt": [{"datei": "/o/a.txt", "alt": True}]}
    stand = indexierung._zwischenstand(neu, alt)
    dateien = [e["datei"] for e in stand]
    pruefe(dateien.count("/o/a.txt") == 2 and not any(e.get("alt") and e["datei"] == "/o/a.txt" for e in stand),
           "fertige Datei kommt ganz hinein, ihr alter Stand nicht")
    pruefe([e for e in stand if e["datei"] == "/o/b.txt"] == alt["/o/b.txt"],
           "halb fertige Datei: nur der alte Stand bleibt")
    pruefe("/o/c.pdf" in dateien, "Datei ohne Inhalt zaehlt als fertig")


def indexlauf_pruefen():
    print("Indexlauf:")
    ordner = os.path.join(_ARBEIT, "dokumente")
    os.makedirs(ordner)
    for name in ("eins", "zwei", "drei"):
        with open(os.path.join(ordner, f"{name}.txt"), "w", encoding="utf-8") as f:
            f.write(f"Das ist das Dokument {name}. " * 40)

    weg = os.path.join(ordner, "zwei.txt")
    dateien = indexierung.dateien_im_ordner(ordner)
    os.remove(weg)   # verschwindet zwischen Durchsuchen und Lesen
    try:
        stand = indexierung.aktualisiere_index(ordner, modell=Probemodell(), dateien=dateien)
        pruefe(True, "verschwundene Datei bricht den Lauf nicht ab")
    except Exception as e:
        stand = []
        pruefe(False, f"verschwundene Datei bricht den Lauf nicht ab ({e})")
    pruefe(weg not in {e["datei"] for e in stand}, "verschwundene Datei steht nicht im Index")
    pruefe(all("vektor" in e for e in stand), "alle Abschnitte haben einen Vektor")

    # Abbruch mitten in der Vektorphase: nichts Halbes darf stehen bleiben.
    for name in ("eins", "drei"):
        with open(os.path.join(ordner, f"{name}.txt"), "a", encoding="utf-8") as f:
            f.write("Neuer Absatz. " * 200)
        neu = time.time() + 5
        os.utime(os.path.join(ordner, f"{name}.txt"), (neu, neu))
    vorher = {e["datei"]: len([x for x in stand if x["datei"] == e["datei"]]) for e in stand}
    abbruch = {"jetzt": False}
    stand = indexierung.aktualisiere_index(
        ordner, modell=Probemodell(abbrechen_nach=1, abbruch=abbruch),
        soll_abbrechen=lambda: abbruch["jetzt"])
    nachher = {}
    for e in stand:
        nachher[e["datei"]] = nachher.get(e["datei"], 0) + 1
    pruefe(all("vektor" in e for e in stand), "nach Abbruch: kein Abschnitt ohne Vektor")
    pruefe(set(nachher) == set(vorher), "nach Abbruch: jede Datei bleibt auffindbar")
    gespeichert = index.lade_bestehenden_index()
    pruefe(len(gespeichert) == len(stand), "nach Abbruch: gespeicherter Index = Rueckgabe")


def entpreller_pruefen():
    print("Ordnerueberwachung:")
    aufrufe = []
    fertig = threading.Event()

    def rueckruf():
        aufrufe.append(time.monotonic())
        fertig.set()

    e = ueberwachung.Entpreller(rueckruf, ruhe=0.15, hoechstens=5)
    beginn = time.monotonic()
    for _ in range(5):
        e.melden()
        time.sleep(0.05)
    fertig.wait(2)
    time.sleep(0.2)
    pruefe(len(aufrufe) == 1, "fuenf Aenderungen kurz hintereinander -> ein Lauf")
    pruefe(aufrufe and aufrufe[0] - beginn >= 0.35, "ausgeloest erst nach der letzten Aenderung")

    pruefe(ueberwachung.ist_relevantes_event("/x/Vertrag.docx"), "Word-Datei ist relevant")
    pruefe(not ueberwachung.ist_relevantes_event("/x/~WRL0003.tmp"), "Word-Hilfsdatei nicht")


def main():
    try:
        einstellungen_pruefen()
        zwischenstand_pruefen()
        indexlauf_pruefen()
        entpreller_pruefen()
    finally:
        shutil.rmtree(_ARBEIT, ignore_errors=True)
    print()
    if FEHLER:
        print(f"{len(FEHLER)} Fall/Faelle nicht wie erwartet.")
        return 1
    print("Alle Robustheitsfaelle wie erwartet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
