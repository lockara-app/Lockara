#!/usr/bin/env python3
"""
lizenz.py - Lizenzdatei pruefen, ohne Internet.

WIE ES FUNKTIONIERT
-------------------
Nach dem Kauf bekommt eine Kanzlei eine kleine Datei (*.lockara-lizenz).
Darin stehen Lizenznehmer, Anzahl der Arbeitsplaetze und Laufzeit - und
eine digitale Unterschrift (Ed25519). Ausgestellt wird sie mit
werkzeuge/lizenz_ausstellen.py und dem PRIVATEN Schluessel, den nur der
Hersteller hat. Die App prueft die Unterschrift mit dem OEFFENTLICHEN
Schluessel aus ressourcen/lizenz/oeffentlicher_schluessel.txt.

Wer auch nur ein Zeichen in der Datei aendert (mehr Arbeitsplaetze, laengere
Laufzeit), macht die Unterschrift ungueltig. Eine neue gueltige Datei kann
nur ausstellen, wer den privaten Schluessel hat.

WARUM OFFLINE
-------------
Lockara verspricht Kanzleien, keine Verbindung nach aussen aufzubauen
(siehe Datenschutz-Einseiter). Eine Lizenzpruefung ueber einen Server
wuerde genau das brechen. Die Datei wird einmal geladen und danach nur noch
lokal geprueft.

WAS BEI ABLAUF PASSIERT
-----------------------
Nichts wird gesperrt. Eine Kanzlei darf nicht mitten in einer Frist von
ihrer Suche ausgesperrt werden. Bis KULANZ_TAGE nach Ablauf gilt die Lizenz
als gueltig (mit Hinweis), danach erscheint ein deutlicher Hinweis zum
Verlaengern - suchen laesst sich weiter. Ob und wie spaeter eingeschraenkt
wird, ist eine Geschaeftsentscheidung; sie gehoert dann hierher
(siehe status()).

AUFBAU DER DATEI
----------------
    {"daten": {"produkt": "Lockara", "format": 1,
               "lizenz_id": "...", "lizenznehmer": "Kanzlei ...",
               "arbeitsplaetze": 5, "ausgestellt": "2026-10-14",
               "gueltig_bis": "2027-10-31"},
     "signatur": "<Base64>"}
Unterschrieben wird die kanonische JSON-Form von "daten" (Schluessel
sortiert, keine Leerzeichen) - siehe kanonisch().
"""

import base64
import datetime
import json
import os
from dataclasses import dataclass, field

from lockara.kern.pfade import DATEN_ORDNER, ressource

PRODUKT = "Lockara"
# Lizenzen, die noch unter dem frueheren Namen SmartSearch ausgestellt
# wurden, bleiben gueltig - der Kunde hat dafuer bezahlt.
FRUEHERE_PRODUKTE = ("SmartSearch",)
FORMAT = 1
DATEIENDUNG = ".lockara-lizenz"
FRUEHERE_DATEIENDUNG = ".smartsearch-lizenz"
KULANZ_TAGE = 30

# Testlizenzen ("art": "test" in den Daten) schalten die Personensuche fuer
# kurze Zeit frei. Sie stellt der Hersteller auf Anfrage per E-Mail aus
# (werkzeuge/lizenz_ausstellen.py --test). Fuer sie gibt es KEINE Kulanz:
# Wer nur testet, verliert mit dem Ablauf nichts, und sonst waeren aus 14
# Testtagen 44 geworden.
ART_TEST = "test"
TEST_TAGE = 14

# Eine Lizenz laesst sich auch als Text weitergeben - als "Lizenzcode", der
# in eine E-Mail passt und in der App eingefuegt wird. Inhalt: dieselbe
# unterschriebene Lizenz wie in der Datei, kompakt und Base64-kodiert.
CODE_PRAEFIX = "LOCKARA-"

# Hier liegt die geladene Lizenz des Nutzers.
LIZENZ_DATEI = os.path.join(DATEN_ORDNER, "lizenz" + DATEIENDUNG)
# So hiess die Datei bei SmartSearch. Nach dem Umzug des Datenordners
# (pfade.py) liegt sie unter diesem Namen im neuen Ordner.
FRUEHERE_LIZENZ_DATEI = os.path.join(DATEN_ORDNER, "lizenz" + FRUEHERE_DATEIENDUNG)

# Der oeffentliche Schluessel des Herstellers. Er wird einmalig mit
#     venv/bin/python -m werkzeuge.lizenz_ausstellen --schluessel-erzeugen
# angelegt und gehoert ins Repository - er ist nicht geheim.
OEFFENTLICHER_SCHLUESSEL = "lizenz/oeffentlicher_schluessel.txt"


@dataclass
class Status:
    """Ergebnis einer Pruefung.

    art: "keine"       - keine Lizenz geladen
         "gueltig"     - Unterschrift stimmt, Laufzeit nicht ueberschritten
         "kulanz"      - abgelaufen, aber noch innerhalb von KULANZ_TAGE
         "abgelaufen"  - abgelaufen und Kulanz vorbei
         "ungueltig"   - Datei kaputt, falsche Unterschrift, falsches Produkt
    """
    art: str
    daten: dict = field(default_factory=dict)
    grund: str = ""

    @property
    def lizenziert(self):
        return self.art in ("gueltig", "kulanz")

    @property
    def ist_test(self):
        return self.daten.get("art") == ART_TEST

    @property
    def gueltig_bis(self):
        try:
            return datetime.date.fromisoformat(self.daten.get("gueltig_bis", ""))
        except ValueError:
            return None


def kanonisch(daten):
    """Die Bytes, die unterschrieben werden. Muss beim Ausstellen und beim
    Pruefen exakt gleich gebildet werden."""
    return json.dumps(daten, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def oeffentlicher_schluessel(pfad=None):
    """Der eingebaute oeffentliche Schluessel (32 Bytes) - oder None, wenn
    noch keiner angelegt wurde."""
    pfad = pfad or ressource(OEFFENTLICHER_SCHLUESSEL)
    try:
        with open(pfad, encoding="utf-8") as f:
            text = "".join(z.strip() for z in f if z.strip() and not z.startswith("#"))
        roh = base64.b64decode(text)
        return roh if len(roh) == 32 else None
    except (OSError, ValueError):
        return None


def pruefen(inhalt, schluessel=None, heute=None):
    """Prueft den Inhalt einer Lizenzdatei (bytes oder str). Gibt immer einen
    Status zurueck, wirft nie."""
    heute = heute or datetime.date.today()
    schluessel = schluessel if schluessel is not None else oeffentlicher_schluessel()
    if schluessel is None:
        return Status("ungueltig", grund="kein_schluessel")
    try:
        if isinstance(inhalt, bytes):
            inhalt = inhalt.decode("utf-8")
        paket = json.loads(inhalt)
        daten = paket["daten"]
        signatur = base64.b64decode(paket["signatur"])
    except (ValueError, KeyError, TypeError):
        return Status("ungueltig", grund="format")

    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        Ed25519PublicKey.from_public_bytes(schluessel).verify(signatur, kanonisch(daten))
    except InvalidSignature:
        return Status("ungueltig", daten=daten, grund="signatur")
    except Exception:
        return Status("ungueltig", daten=daten, grund="format")

    if daten.get("produkt") not in (PRODUKT,) + FRUEHERE_PRODUKTE or daten.get("format") != FORMAT:
        return Status("ungueltig", daten=daten, grund="produkt")

    status = Status("gueltig", daten=daten)
    bis = status.gueltig_bis
    if bis is None:
        return Status("ungueltig", daten=daten, grund="format")
    kulanz = 0 if daten.get("art") == ART_TEST else KULANZ_TAGE
    if heute > bis + datetime.timedelta(days=kulanz):
        status.art = "abgelaufen"
    elif heute > bis:
        status.art = "kulanz"
    return status


def als_code(inhalt):
    """Lizenzdatei-Inhalt -> Lizenzcode zum Einfuegen ("LOCKARA-...")."""
    if isinstance(inhalt, bytes):
        inhalt = inhalt.decode("utf-8")
    paket = json.loads(inhalt)
    kompakt = json.dumps(paket, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return CODE_PRAEFIX + base64.urlsafe_b64encode(kompakt.encode("utf-8")).decode().rstrip("=")


def aus_code(code):
    """Lizenzcode -> Inhalt einer Lizenzdatei (bytes), oder None.

    Leerzeichen und Zeilenumbrueche werden ignoriert: E-Mail-Programme
    brechen lange Zeilen gern um, und beim Kopieren rutscht oft ein
    Leerzeichen mit."""
    text = "".join((code or "").split())
    if text.upper().startswith(CODE_PRAEFIX):
        text = text[len(CODE_PRAEFIX):]
    if not text:
        return None
    try:
        roh = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
        json.loads(roh.decode("utf-8"))
        return roh
    except (ValueError, UnicodeDecodeError):
        return None


def _speichern(inhalt):
    os.makedirs(DATEN_ORDNER, exist_ok=True)
    # Genau die geprueften Bytes schreiben, nicht die Quelle ein zweites
    # Mal kopieren - sonst koennte zwischen Pruefen und Kopieren eine
    # andere Datei an ihrer Stelle liegen.
    ziel_tmp = LIZENZ_DATEI + ".tmp"
    with open(ziel_tmp, "wb") as f:
        f.write(inhalt)
    os.replace(ziel_tmp, LIZENZ_DATEI)


def code_installieren(code):
    """Wie installieren(), aber mit einem Lizenzcode statt einer Datei.

    Eine abgelaufene Testlizenz ersetzt nie eine gueltige Lizenz - wer
    einen alten Testcode noch einmal einfuegt, soll seine gekaufte Lizenz
    nicht verlieren."""
    inhalt = aus_code(code)
    if inhalt is None:
        return Status("ungueltig", grund="format")
    ergebnis = pruefen(inhalt)
    if ergebnis.lizenziert or (ergebnis.art == "abgelaufen" and not status().lizenziert):
        _speichern(inhalt)
    return ergebnis


def _fruehere_lizenz_umbenennen():
    """Gibt einer von SmartSearch uebernommenen Lizenzdatei den neuen Namen."""
    if os.path.exists(FRUEHERE_LIZENZ_DATEI) and not os.path.exists(LIZENZ_DATEI):
        try:
            os.replace(FRUEHERE_LIZENZ_DATEI, LIZENZ_DATEI)
        except OSError:
            pass


def status(heute=None):
    """Die Lizenz dieses Rechners."""
    _fruehere_lizenz_umbenennen()
    if not os.path.exists(LIZENZ_DATEI):
        return Status("keine")
    try:
        with open(LIZENZ_DATEI, "rb") as f:
            return pruefen(f.read(), heute=heute)
    except OSError:
        return Status("ungueltig", grund="lesen")


def installieren(quelle):
    """Prueft eine Lizenzdatei und legt sie, wenn sie gueltig ist (auch in
    der Kulanzzeit), in den Datenordner. Gibt den Status zurueck; eine
    ungueltige Datei ersetzt nie eine vorhandene."""
    try:
        with open(quelle, "rb") as f:
            inhalt = f.read()
    except OSError:
        return Status("ungueltig", grund="lesen")
    ergebnis = pruefen(inhalt)
    if ergebnis.art in ("gueltig", "kulanz", "abgelaufen"):
        _speichern(inhalt)
    return ergebnis
