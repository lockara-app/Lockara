#!/usr/bin/env python3
"""
pfade.py - zentrale Ablage aller Nutzerdaten von Lockara.

WARUM ES DIESE DATEI GIBT
-------------------------
Frueher lagen Index, Konfiguration, Favoriten und Suchverlauf direkt neben
gui.py, also im Programmordner. Solange man die App aus dem Quellcode
startet, faellt das nicht auf. In einer gebauten .app ist es aber ein
handfestes Problem:

1. Ein Update bedeutet auf dem Mac "alte .app in den Papierkorb, neue
   hineinziehen" - damit waeren alle Einstellungen und der komplette Index
   weg, und jeder Nutzer muesste nach jedem Update alles neu einlesen.
2. Sobald die App signiert ist, bricht jedes Schreiben ins eigene Bundle
   die Signatur. macOS verweigert den Start dann komplett.
3. Liegt die App in /Applications, hat ein normaler Nutzer dort gar keine
   Schreibrechte.

Deshalb liegt ab jetzt alles an dem Ort, den macOS dafuer vorsieht:

    ~/Library/Application Support/Lockara/

Der ueberlebt Updates, Verschieben der App und das Signieren.

MIGRATION
---------
Damit bestehende Installationen (und Marcels eigener Arbeitsordner) beim
Umstieg nicht bei null anfangen, werden vorhandene Dateien aus dem alten
Ort einmalig herueberkopiert - kopiert, nicht verschoben, damit ein
Fehlschlag nichts zerstoert. Passiert genau einmal; danach existiert die
Zieldatei und die Migration ueberspringt sie.
"""

import os
import shutil
import sys

APP_NAME = "Lockara"

# Bis Fassung 1.0.8 hiess das Programm SmartSearch. Alles, was Nutzer
# davon noch auf dem Rechner haben (Datenordner, Lizenz, Autostart,
# Umgebungsvariablen), wird ueber diese Namen wiedergefunden und beim
# ersten Start von Lockara uebernommen.
FRUEHERER_APP_NAME = "SmartSearch"

# Projektordner (dort liegen ressourcen/, tests/, werkzeuge/ ...). Diese
# Datei liegt in lockara/kern/, also zwei Ebenen darunter.
PROJEKT_ORDNER = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Alter Ablageort der Nutzerdaten: bis zur Einfuehrung dieser Datei lagen
# index.pkl & Co. direkt im Projektordner neben gui.py.
_ALTER_ORDNER = PROJEKT_ORDNER


# ---------------------------------------------------------------------------
# PROGRAMM-RESSOURCEN (Symbole usw.)
#
# Nicht zu verwechseln mit den Nutzerdaten weiter unten: Ressourcen gehoeren
# zum Programm und werden mit ausgeliefert, Nutzerdaten entstehen beim
# Benutzen.
#
# Warum eine eigene Funktion: Beim Start aus dem Quelltext liegen die
# Symbole in ressourcen/ im Projektordner. In der gebauten App packt
# PyInstaller sie in einen eigenen Ordner, den es zur Laufzeit in
# sys._MEIPASS nennt. Vorher stand an drei Stellen im Code
# "os.path.dirname(__file__) + icon.png" - in der gebauten App zeigte das
# ins Leere, weil icon.png dort gar nicht mitgepackt war. Unter Windows
# haette das Fenster deshalb nie ein eigenes Symbol bekommen.
# ---------------------------------------------------------------------------

def ressource(relativer_pfad):
    """Absoluter Pfad einer mitgelieferten Datei, z. B. ressource("icons/icon.png")."""
    basis = getattr(sys, "_MEIPASS", None)
    if basis:
        return os.path.join(basis, "ressourcen", relativer_pfad)
    return os.path.join(PROJEKT_ORDNER, "ressourcen", relativer_pfad)


def umgebung(name):
    """Liest eine Einstellung aus einer Umgebungsvariable LOCKARA_<name>.

    Aeltere Skripte und Messungen setzen noch SMARTSEARCH_<name>; die gilt
    weiter, wenn die neue Variable fehlt.
    """
    wert = os.environ.get("LOCKARA_" + name)
    if wert is None:
        wert = os.environ.get("SMARTSEARCH_" + name)
    return wert


def _ermittle_daten_ordner(app_name=APP_NAME):
    """Der Ort, den das jeweilige System fuer Programmdaten vorsieht.

    macOS:   ~/Library/Application Support/Lockara
    Windows: %LOCALAPPDATA%\\Lockara
    sonst:   ~/.lockara

    Unter Windows ist das nicht nur Geschmackssache: LOCALAPPDATA ist der
    Ordner, den ein Nutzer OHNE Administratorrechte beschreiben darf, und
    den eine Firma bei servergespeicherten Profilen bewusst NICHT mit
    synchronisiert. Ein Index von mehreren hundert Megabyte hat in einem
    wandernden Profil nichts zu suchen - er wuerde bei jeder Anmeldung
    durchs Netz kopiert.

    Faellt in allen Faellen auf ~/.lockara zurueck, wenn der
    vorgesehene Ort nicht existiert - besser ein unuebliches Verzeichnis
    als ein Absturz beim Start.
    """
    # Fuer Messungen und Tests: ein eigener, leerer Datenordner, damit der
    # echte Index des Nutzers nicht angefasst wird (werkzeuge/modellvergleich.py).
    eigener = umgebung("DATENORDNER")
    if eigener and app_name == APP_NAME:
        return os.path.abspath(os.path.expanduser(eigener))

    if os.name == "nt":
        basis = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if basis and os.path.isdir(basis):
            return os.path.join(basis, app_name)
        return os.path.expanduser("~/." + app_name.lower())

    basis = os.path.expanduser("~/Library/Application Support")
    if not os.path.isdir(basis):
        return os.path.expanduser("~/." + app_name.lower())
    return os.path.join(basis, app_name)


DATEN_ORDNER = _ermittle_daten_ordner()

# Wo SmartSearch (bis 1.0.8) seine Daten abgelegt hat. Ist bei einem
# eigenen Datenordner (Tests, Messungen) None - dann gibt es nichts umzuziehen.
FRUEHERER_DATEN_ORDNER = (None if umgebung("DATENORDNER")
                          else _ermittle_daten_ordner(FRUEHERER_APP_NAME))

INDEX_FILE = os.path.join(DATEN_ORDNER, "index.pkl")
CONFIG_FILE = os.path.join(DATEN_ORDNER, "config.json")
FAVORITEN_FILE = os.path.join(DATEN_ORDNER, "favoriten.json")
VERLAUF_FILE = os.path.join(DATEN_ORDNER, "verlauf.json")

# Dateiname -> Zielpfad. Reihenfolge egal, alle werden einzeln geprueft.
_ZU_MIGRIEREN = {
    "index.pkl": INDEX_FILE,
    "config.json": CONFIG_FILE,
    "favoriten.json": FAVORITEN_FILE,
    "verlauf.json": VERLAUF_FILE,
}


def _frueheren_datenordner_uebernehmen():
    """Zieht beim ersten Start von Lockara den Datenordner von SmartSearch um.

    Index (oft mehrere hundert MB), Einstellungen, Favoriten, Verlauf und
    eine geladene Lizenz liegen dort. Ohne Umzug muesste jeder bisherige
    Nutzer alle Ordner neu einlesen lassen.

    Verschoben statt kopiert: Der Index kann sehr gross sein, und auf
    demselben Laufwerk ist Umbenennen sofort fertig. Klappt das nicht
    (z. B. anderes Laufwerk), wird kopiert - der alte Ordner bleibt dann
    stehen, nichts geht verloren. Laeuft nur, solange es den neuen Ordner
    noch nicht gibt; ein spaeterer Start ueberschreibt also nie neue Daten.
    """
    alt = FRUEHERER_DATEN_ORDNER
    if not alt or alt == DATEN_ORDNER or not os.path.isdir(alt) or os.path.exists(DATEN_ORDNER):
        return
    try:
        os.makedirs(os.path.dirname(DATEN_ORDNER), exist_ok=True)
        os.rename(alt, DATEN_ORDNER)
        print(f"[Info] Daten von {FRUEHERER_APP_NAME} uebernommen: {alt} -> {DATEN_ORDNER}")
    except OSError:
        try:
            shutil.copytree(alt, DATEN_ORDNER)
            print(f"[Info] Daten von {FRUEHERER_APP_NAME} kopiert: {alt} -> {DATEN_ORDNER}")
        except Exception as e:
            print(f"[Warnung] Daten von {FRUEHERER_APP_NAME} konnten nicht uebernommen werden: {e}")


def stelle_datenordner_sicher():
    """Legt den Datenordner an und holt einmalig alte Daten herueber.

    Wird beim Import dieses Moduls aufgerufen, also automatisch beim
    Programmstart - egal ueber welchen Einstieg. Schlaegt bewusst
    nie hart fehl: kann der Ordner nicht angelegt werden, laeuft die App
    trotzdem weiter und meldet das Problem erst dort, wo wirklich
    geschrieben wird.
    """
    _frueheren_datenordner_uebernehmen()
    try:
        os.makedirs(DATEN_ORDNER, exist_ok=True)
    except Exception as e:
        print(f"[Warnung] Datenordner konnte nicht angelegt werden ({DATEN_ORDNER}): {e}")
        return

    for dateiname, ziel in _ZU_MIGRIEREN.items():
        quelle = os.path.join(_ALTER_ORDNER, dateiname)
        # Nur migrieren, wenn es am alten Ort etwas gibt UND am neuen Ort
        # noch nichts steht - sonst wuerde ein spaeterer Start frische
        # Daten mit einem alten Stand ueberschreiben.
        if not os.path.exists(quelle) or os.path.exists(ziel):
            continue
        try:
            shutil.copy2(quelle, ziel)
            print(f"[Info] {dateiname} in den Datenordner uebernommen.")
        except Exception as e:
            print(f"[Warnung] {dateiname} konnte nicht uebernommen werden: {e}")


stelle_datenordner_sicher()
