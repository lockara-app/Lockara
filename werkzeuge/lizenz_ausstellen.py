#!/usr/bin/env python3
"""
lizenz_ausstellen.py - Lizenzdateien fuer Kunden ausstellen.

EINMALIG: Schluesselpaar anlegen
    venv/bin/python -m werkzeuge.lizenz_ausstellen --schluessel-erzeugen

    Der PRIVATE Schluessel landet in ~/.lockara-lizenz/privat.key
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

    Ergebnis: eine Datei *.lockara-lizenz im aktuellen Ordner, die Sie
    der Kanzlei schicken. Sie laedt sie in Lockara unter
    Einstellungen > Lizenz.

PRUEFEN
    venv/bin/python -m werkzeuge.lizenz_ausstellen --pruefen datei.lockara-lizenz

TESTLIZENZ AUF ANFRAGE (14 Tage, gibt eine fertige Antwort-E-Mail aus)
    venv/bin/python -m werkzeuge.lizenz_ausstellen --test --lizenznehmer "Kanzlei Muster"
"""

import argparse
import base64
import datetime
import json
import os
import re
import sys
import uuid

from lockara.kern import lizenz
from lockara.kern.pfade import PROJEKT_ORDNER

PRIVAT_ORDNER = os.path.expanduser("~/.lockara-lizenz")
PRIVAT_DATEI = os.path.join(PRIVAT_ORDNER, "privat.key")

# Vor der Umbenennung lag der Schluessel in ~/.smartsearch-lizenz. Er
# gehoert zum oeffentlichen Schluessel im Repository und darf nicht
# verloren gehen - deshalb wird er dort weiter gefunden, solange am neuen
# Ort keiner liegt. Ein neuer Schluessel wuerde alle ausgestellten
# Lizenzen ungueltig machen.
_FRUEHERE_PRIVAT_DATEI = os.path.expanduser("~/.smartsearch-lizenz/privat.key")
if not os.path.exists(PRIVAT_DATEI) and os.path.exists(_FRUEHERE_PRIVAT_DATEI):
    PRIVAT_ORDNER = os.path.dirname(_FRUEHERE_PRIVAT_DATEI)
    PRIVAT_DATEI = _FRUEHERE_PRIVAT_DATEI
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
        f.write("# Oeffentlicher Schluessel fuer Lockara-Lizenzen (Ed25519).\n"
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


def ausstellen(lizenznehmer, arbeitsplaetze, gueltig_bis, privat=PRIVAT_DATEI, heute=None, test=False):
    """Gibt den Inhalt einer Lizenzdatei (str) zurueck. test=True stellt eine
    Testlizenz aus (ohne Kulanz nach Ablauf, siehe kern/lizenz.py)."""
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
    if test:
        daten["art"] = lizenz.ART_TEST
    signatur = _privater_schluessel(privat).sign(lizenz.kanonisch(daten))
    return json.dumps({"daten": daten, "signatur": base64.b64encode(signatur).decode()},
                      ensure_ascii=False, indent=2) + "\n"


def _dateiname(lizenznehmer, gueltig_bis):
    kurz = re.sub(r"[^A-Za-z0-9]+", "-", lizenznehmer).strip("-")[:40] or "Lizenz"
    return f"Lockara-{kurz}-bis-{gueltig_bis}{lizenz.DATEIENDUNG}"


def main():
    p = argparse.ArgumentParser(description="Lockara-Lizenzen ausstellen")
    p.add_argument("--schluessel-erzeugen", action="store_true")
    p.add_argument("--ueberschreiben", action="store_true")
    p.add_argument("--lizenznehmer")
    p.add_argument("--arbeitsplaetze", type=int)
    p.add_argument("--gueltig-bis", help="JJJJ-MM-TT")
    p.add_argument("--pruefen", metavar="DATEI")
    p.add_argument("--test", action="store_true",
                   help=f"Testlizenz: 1 Arbeitsplatz, {lizenz.TEST_TAGE} Tage, gibt den Code fuer die E-Mail aus")
    p.add_argument("--code", action="store_true", help="zusaetzlich den Lizenzcode ausgeben")
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
    if a.test:
        if not a.lizenznehmer:
            p.error("--lizenznehmer angeben (Name der Kanzlei oder Firma)")
        bis = (datetime.date.today() + datetime.timedelta(days=lizenz.TEST_TAGE)).isoformat()
        inhalt = ausstellen(a.lizenznehmer, a.arbeitsplaetze or 1, a.gueltig_bis or bis, test=True)
        print(mail_text(a.lizenznehmer, a.gueltig_bis or bis, lizenz.als_code(inhalt)))
        return
    if not (a.lizenznehmer and a.arbeitsplaetze and a.gueltig_bis):
        p.error("--lizenznehmer, --arbeitsplaetze und --gueltig-bis angeben")
    inhalt = ausstellen(a.lizenznehmer, a.arbeitsplaetze, a.gueltig_bis)
    name = _dateiname(a.lizenznehmer, a.gueltig_bis)
    with open(name, "w", encoding="utf-8") as f:
        f.write(inhalt)
    print(f"Ausgestellt: {os.path.abspath(name)}")
    if a.code:
        print(f"\nLizenzcode:\n{lizenz.als_code(inhalt)}")


def mail_text(lizenznehmer, gueltig_bis, code):
    """Fertige Antwort auf eine Testanfrage - zum Kopieren in die E-Mail."""
    bis = datetime.date.fromisoformat(gueltig_bis).strftime("%d.%m.%Y")
    return f"""---------------- E-Mail zum Kopieren ----------------
Betreff: Ihre Testlizenz für die Lockara-Personensuche

Guten Tag,

vielen Dank für Ihr Interesse. Hier ist Ihre Testlizenz für {lizenznehmer},
gültig bis {bis}:

{code}

So schalten Sie die Personensuche frei:
1. Lockara öffnen und links auf „Personensuche (DSGVO)“ klicken.
2. Den Code oben vollständig kopieren und in das Feld „Lizenzcode“ einfügen.
3. Auf „Freischalten“ klicken.

Die normale Suche bleibt auch nach dem Testzeitraum unverändert nutzbar.
Bei Fragen antworten Sie einfach auf diese E-Mail.

Viele Grüße
Marcel Landmann
Lockara · kontakt@lockara.de
------------------------------------------------------"""


if __name__ == "__main__":
    main()
