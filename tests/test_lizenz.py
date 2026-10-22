# -*- coding: utf-8 -*-
"""Prueft Ausstellen und Pruefen von Lizenzdateien - mit einem eigenen,
nur fuer diesen Test erzeugten Schluesselpaar. Der echte private Schluessel
wird nie angefasst.

Aufruf (im Projektordner):   venv/bin/python -m tests.test_lizenz
"""

import datetime
import json
import os
import sys
import tempfile

from lockara.kern import lizenz
from werkzeuge import lizenz_ausstellen as aussteller


def main():
    ordner = tempfile.mkdtemp(prefix="lockara-lizenztest-")
    privat = os.path.join(ordner, "privat.key")
    oeffentlich = os.path.join(ordner, "oeffentlich.txt")
    aussteller.schluessel_erzeugen(privat, oeffentlich)
    schluessel = lizenz.oeffentlicher_schluessel(oeffentlich)
    heute = datetime.date(2026, 10, 14)

    def stelle_aus(bis, plaetze=5, name="Kanzlei Test & Partner"):
        return aussteller.ausstellen(name, plaetze, bis, privat=privat, heute=heute)

    fehler = 0

    def erwarte(beschreibung, inhalt, art, grund="", tag=heute, mit=schluessel):
        nonlocal fehler
        s = lizenz.pruefen(inhalt, schluessel=mit, heute=tag)
        ok = s.art == art and (not grund or s.grund == grund)
        if not ok:
            fehler += 1
        print(f"  {'ok  ' if ok else 'FEHL'} {beschreibung:52} -> {s.art} {s.grund}")

    gut = stelle_aus("2027-10-31")
    erwarte("gueltige Lizenz", gut, "gueltig")
    erwarte("am letzten Tag", gut, "gueltig", tag=datetime.date(2027, 10, 31))
    erwarte("einen Tag nach Ablauf: Kulanz", gut, "kulanz", tag=datetime.date(2027, 11, 1))
    erwarte("30 Tage nach Ablauf: noch Kulanz", gut, "kulanz", tag=datetime.date(2027, 11, 30))
    erwarte("31 Tage nach Ablauf: abgelaufen", gut, "abgelaufen", tag=datetime.date(2027, 12, 1))

    paket = json.loads(gut)
    paket["daten"]["arbeitsplaetze"] = 50
    erwarte("Arbeitsplaetze nachtraeglich erhoeht", json.dumps(paket), "ungueltig", "signatur")

    paket = json.loads(gut)
    paket["daten"]["gueltig_bis"] = "2099-12-31"
    erwarte("Laufzeit nachtraeglich verlaengert", json.dumps(paket), "ungueltig", "signatur")

    erwarte("kaputte Datei", "kein json", "ungueltig", "format")
    erwarte("ohne eingebauten Schluessel", gut, "ungueltig", "kein_schluessel", mit=None)

    fremd_ordner = tempfile.mkdtemp(prefix="lockara-lizenztest-fremd-")
    fremd_privat = os.path.join(fremd_ordner, "privat.key")
    aussteller.schluessel_erzeugen(fremd_privat, os.path.join(fremd_ordner, "o.txt"))
    fremd = aussteller.ausstellen("Kanzlei Test", 5, "2027-10-31", privat=fremd_privat, heute=heute)
    erwarte("mit fremdem Schluessel ausgestellt", fremd, "ungueltig", "signatur")

    # --- Testlizenz und Lizenzcode ---
    test = aussteller.ausstellen("Kanzlei Probe", 1, "2026-10-28", privat=privat, heute=heute, test=True)
    erwarte("Testlizenz gueltig", test, "gueltig")
    erwarte("Testlizenz einen Tag nach Ablauf: ohne Kulanz", test, "abgelaufen",
            tag=datetime.date(2026, 10, 29))
    if not lizenz.pruefen(test, schluessel=schluessel, heute=heute).ist_test:
        fehler += 1
        print("  FEHL Testlizenz wird nicht als Test erkannt")
    paket = json.loads(test)
    del paket["daten"]["art"]
    erwarte("Testvermerk entfernt (dann Kulanz erschlichen)", json.dumps(paket), "ungueltig", "signatur")

    code = lizenz.als_code(test)
    umgebrochen = code[:30] + "\n " + code[30:70] + " \r\n" + code[70:]
    for name, c in (("Lizenzcode", code), ("Lizenzcode mit Umbruechen", umgebrochen),
                    ("Lizenzcode klein geschrieben (Praefix)", "lockara-" + code[len(lizenz.CODE_PRAEFIX):])):
        erwarte(name, lizenz.aus_code(c) or b"", "gueltig")
    erwarte("Lizenzcode abgeschnitten", lizenz.aus_code(code[:-20]) or b"kaputt", "ungueltig")
    if lizenz.aus_code("Hallo Welt") is not None:
        fehler += 1
        print("  FEHL Unsinn wurde als Code angenommen")

    if fehler:
        print(f"{fehler} Faelle weichen ab.")
        return 1
    print("Alle Lizenzfaelle wie erwartet.")
    return 0


if __name__ == "__main__":
    # Ohne eingebauten Schluessel liefert pruefen(schluessel=None) den
    # Fall "kein_schluessel" - dafuer den Pfad auf eine leere Stelle biegen.
    lizenz.OEFFENTLICHER_SCHLUESSEL = "lizenz/gibt-es-nicht.txt"
    sys.exit(main())
