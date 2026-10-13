#!/usr/bin/env python3
"""
lizenz_ausstellen.py - Lizenzdateien fuer Kunden ausstellen.

EINMALIG: Schluesselpaar anlegen
    venv/bin/python -m werkzeuge.lizenz_ausstellen --schluessel-erzeugen

    Der PRIVATE Schluessel landet in ~/.smartsearch-lizenz/privat.key
    (nur fuer Sie lesbar). Er darf nie ins Repository, nie in eine Mail,
    nie in die App. Wer ihn hat, kann beliebige Lizenzen ausstellen -
    unbedingt sichern (z. B. Passwortmanager), denn ohne ihn lassen sich
    keine Lizenzen mehr ausstellen, die bestehende Apps anerkennen.

    Der OEFFENTLICHE Schluessel wird nach
    ressourcen/lizenz/oeffentlicher_schluessel.txt geschrieben. Diese Datei
    gehoert ins Repository und in jede ausgelieferte App.

LIZENZ AUSSTELLEN
    venv/bin/python -m werkzeuge.lizenz_ausstellen \\
        --lizenznehmer "Kanzlei Mustermann & Partner" \\
        --arbeitsplaetze 5 --gueltig-bis 2027-10-31

    Ergebnis: eine Datei *.smartsearch-lizenz im aktuellen Ordner, die Sie
    der Kanzlei schicken. Sie laedt sie in SmartSearch unter
    Einstellungen > Lizenz.

PRUEFEN
    venv/bin/python -m werkzeuge.lizenz_ausstellen --pruefen datei.smartsearch-lizenz
"""

import argparse
import base64
import datetime
import json
import os
import re
import sys
import uuid

from smartsearch.kern import lizenz
from smartsearch.kern.pfade import PROJEKT_ORDNER

PRIVAT_ORDNER = os.path.expanduser("~/.smartsearch-lizenz")
PRIVAT_DATEI = os.path.join(PRIVAT_ORDNER, "privat.key")
OEFFENTLICH_DATEI = os.path.join(PROJEKT_ORDNER, "ressourcen", lizenz.OEFFENTLICHER_SCHLUESSEL)


def schluessel_erzeugen(privat=PRIVAT_DATEI, oeffentlich=OEFFENTLICH_DATEI, ueberschreiben=False):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    if os.path.exists(privat) and not ueberschreiben:
        raise SystemExit(
            f"Es gibt schon einen privaten Schluessel: {privat}\n"
            "Ein neuer wuerde alle bisher ausgestellten Lizenzen ungueltig machen.\n"
            "Wenn das wirklich gewollt ist: --ueberschreiben")
    schluessel = Ed25519PrivateKey.generate()
    roh_privat = schluessel.private_bytes(serialization.Encoding.Raw,
                                          serialization.PrivateFormat.Raw,
                                          serialization.NoEncryption())
    roh_oeffentlich = schluessel.public_key().public_bytes(serialization.Encoding.Raw,
                                                           serialization.PublicFormat.Raw)
    os.makedirs(os.path.dirname(privat), exist_ok=True)
    os.chmod(os.path.dirname(privat), 0o700)
    with open(privat, "w", encoding="utf-8") as f:
        f.write(base64.b64encode(roh_privat).decode() + "\n")
    os.chmod(privat, 0o600)
    os.makedirs(os.path.dirname(oeffentlich), exist_ok=True)
    with open(oeffentlich, "w", encoding="utf-8") as f:
        f.write("# Oeffentlicher Schluessel fuer SmartSearch-Lizenzen (Ed25519).\n"
                "# Nicht geheim. Erzeugt mit werkzeuge/lizenz_ausstellen.py.\n"
                + base64.b64encode(roh_oeffentlich).decode() + "\n")
    return privat, oeffentlich


def _privater_schluessel(pfad=PRIVAT_DATEI):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    try:
        with open(pfad, encoding="utf-8") as f:
            return Ed25519PrivateKey.from_private_bytes(base64.b64decode(f.read().strip()))
    except FileNotFoundError:
        raise SystemExit(f"Kein privater Schluessel unter {pfad}. Zuerst: --schluessel-erzeugen")


def ausstellen(lizenznehmer, arbeitsplaetze, gueltig_bis, privat=PRIVAT_DATEI, heute=None):
    """Gibt den Inhalt einer Lizenzdatei (str) zurueck."""
    if arbeitsplaetze < 1:
        raise ValueError("arbeitsplaetze muss mindestens 1 sein")
    datetime.date.fromisoformat(gueltig_bis)   # wirft bei falschem Datum
    daten = {
        "produkt": lizenz.PRODUKT,
        "format": lizenz.FORMAT,
        "lizenz_id": uuid.uuid4().hex[:12],
        "lizenznehmer": lizenznehmer.strip(),
        "arbeitsplaetze": int(arbeitsplaetze),
        "ausgestellt": (heute or datetime.date.today()).isoformat(),
        "gueltig_bis": gueltig_bis,
    }
    signatur = _privater_schluessel(privat).sign(lizenz.kanonisch(daten))
    return json.dumps({"daten": daten, "signatur": base64.b64encode(signatur).decode()},
                      ensure_ascii=False, indent=2) + "\n"


def _dateiname(lizenznehmer, gueltig_bis):
    kurz = re.sub(r"[^A-Za-z0-9]+", "-", lizenznehmer).strip("-")[:40] or "Lizenz"
    return f"SmartSearch-{kurz}-bis-{gueltig_bis}{lizenz.DATEIENDUNG}"


def main():
    p = argparse.ArgumentParser(description="SmartSearch-Lizenzen ausstellen")
    p.add_argument("--schluessel-erzeugen", action="store_true")
    p.add_argument("--ueberschreiben", action="store_true")
    p.add_argument("--lizenznehmer")
    p.add_argument("--arbeitsplaetze", type=int)
    p.add_argument("--gueltig-bis", help="JJJJ-MM-TT")
    p.add_argument("--pruefen", metavar="DATEI")
    a = p.parse_args()

    if a.schluessel_erzeugen:
        privat, oeffentlich = schluessel_erzeugen(ueberschreiben=a.ueberschreiben)
        print(f"Privater Schluessel:    {privat}   (geheim halten, sichern!)")
        print(f"Oeffentlicher Schluessel: {oeffentlich}   (committen)")
        return
    if a.pruefen:
        with open(a.pruefen, "rb") as f:
            s = lizenz.pruefen(f.read())
        print(f"{s.art}{' (' + s.grund + ')' if s.grund else ''}")
        for k, v in s.daten.items():
            print(f"  {k}: {v}")
        sys.exit(0 if s.lizenziert else 1)
    if not (a.lizenznehmer and a.arbeitsplaetze and a.gueltig_bis):
        p.error("--lizenznehmer, --arbeitsplaetze und --gueltig-bis angeben")
    inhalt = ausstellen(a.lizenznehmer, a.arbeitsplaetze, a.gueltig_bis)
    name = _dateiname(a.lizenznehmer, a.gueltig_bis)
    with open(name, "w", encoding="utf-8") as f:
        f.write(inhalt)
    print(f"Ausgestellt: {os.path.abspath(name)}")


if __name__ == "__main__":
    main()
