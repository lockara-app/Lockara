#!/usr/bin/env python3
"""
ueberwachung.py - bemerkt Aenderungen in den ueberwachten Ordnern und
stoesst dann eine Aktualisierung des Index an.

Laeuft ueber watchdog. Fehlt das Paket, gibt es eben keine automatische
Aktualisierung - der Knopf "Index aktualisieren" funktioniert trotzdem.
"""

import os
import threading
import time

from lockara.kern.dateien import IGNORIERTE_ORDNERNAMEN, UNTERSTUETZT
from lockara.kern.einstellungen import lade_config

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_VERFUEGBAR = True
except ImportError:
    WATCHDOG_VERFUEGBAR = False


# Ordner-/Datei-Fragmente, die NIE einen Re-Index auslösen sollen. Das sind
# typische App-eigene Pfade (venv, .git, __pycache__) und die eigenen
# Datenablagen der App (verlauf.json, Index-/Cache-Dateien). Ohne diesen
# Filter löst die App durch ihr eigenes Schreiben (Index speichern, Verlauf
# speichern) ständig neue Watchdog-Events aus und indexiert sich selbst in
# eine Endlosschleife.
#
# Die Ordnernamen kommen aus dateien.IGNORIERTE_ORDNERNAMEN - dieselbe
# Liste, die auch das Einlesen benutzt. Frueher stand hier eine eigene,
# fast gleiche Liste; was in der einen fehlte, loeste in der anderen
# unnoetige Laeufe aus.
IGNORIERTE_PFAD_FRAGMENTE = {os.sep + name + os.sep for name in IGNORIERTE_ORDNERNAMEN}
IGNORIERTE_DATEINAMEN = {
    "verlauf.json",
    "favoriten.json",
    ".ds_store",
}


def ist_relevantes_event(dateipfad):
    """True nur für Dateien, die tatsächlich neu indexiert werden müssten
    (unterstützte Dokumenttypen) und die nicht zu App-eigenen Daten gehören."""
    name = os.path.basename(dateipfad).lower()
    if name in IGNORIERTE_DATEINAMEN or name.startswith("."):
        return False

    normiert = os.sep + dateipfad.replace("/", os.sep).strip(os.sep) + os.sep
    if any(frag in normiert for frag in IGNORIERTE_PFAD_FRAGMENTE):
        return False

    ext = os.path.splitext(name)[1]
    return ext in UNTERSTUETZT


# Wie lange es nach der LETZTEN Aenderung ruhig sein muss, bevor neu
# indexiert wird - und wie lange hoechstens gewartet wird, wenn es nie
# ruhig wird (ein Ordner, in den laufend etwas synchronisiert wird).
#
# Frueher loeste die ERSTE Aenderung sofort aus, und alles in den folgenden
# fuenf Sekunden wurde verworfen. Beim Kopieren mehrerer Dateien las der
# Lauf dadurch die erste, oft noch halb geschriebene Datei - und die
# uebrigen erst beim naechsten, zufaelligen Anlass. Jetzt wird gewartet,
# bis Ruhe ist.
RUHEZEIT_SEK = 4
HOECHSTENS_WARTEN_SEK = 30


class Entpreller:
    """Fasst viele Aenderungen zu EINEM Aufruf zusammen: ausgeloest wird
    RUHEZEIT_SEK nach der letzten Meldung, spaetestens aber
    HOECHSTENS_WARTEN_SEK nach der ersten. Laeuft in eigenen Threads -
    der Rueckruf kommt also aus einem fremden Thread (siehe Ordnerwaechter)."""

    def __init__(self, rueckruf, ruhe=RUHEZEIT_SEK, hoechstens=HOECHSTENS_WARTEN_SEK):
        self._rueckruf = rueckruf
        self._ruhe = ruhe
        self._hoechstens = hoechstens
        self._lock = threading.Lock()
        self._timer = None
        self._erste_meldung = None

    def melden(self):
        with self._lock:
            jetzt = time.monotonic()
            if self._erste_meldung is None:
                self._erste_meldung = jetzt
            if self._timer is not None:
                self._timer.cancel()
            warten = min(self._ruhe, max(0.0, self._erste_meldung + self._hoechstens - jetzt))
            self._timer = threading.Timer(warten, self._ausloesen)
            self._timer.daemon = True
            self._timer.start()

    def _ausloesen(self):
        with self._lock:
            self._timer = None
            self._erste_meldung = None
        try:
            self._rueckruf()
        except Exception as e:
            print(f"[Ueberwachung] Aktualisierung nicht angestossen: {e}")

    def abbrechen(self):
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = None
            self._erste_meldung = None


if WATCHDOG_VERFUEGBAR:
    class OrdnerAenderungsHandler(FileSystemEventHandler):
        def __init__(self, entpreller):
            super().__init__()
            self.entpreller = entpreller

        def on_any_event(self, event):
            if event.is_directory:
                return
            # Nur auf relevante Dokumenttypen reagieren - alles andere
            # (Index-Dateien, verlauf.json, venv, .git, ...) ignorieren,
            # sonst löst die App durch ihr eigenes Schreiben permanent
            # neue Re-Indexierungen aus.
            #
            # Bei einem Umbenennen zaehlt auch das ZIEL. Word, Excel und
            # viele andere Programme speichern erst in eine Hilfsdatei und
            # benennen sie dann um ("~WRL0003.tmp" -> "Vertrag.docx"). Die
            # Quelle ist dabei irrelevant - nur auf sie zu schauen hiess,
            # dass genau das normale Speichern aus Word nie bemerkt wurde.
            pfade = [event.src_path, getattr(event, "dest_path", "")]
            if any(p and ist_relevantes_event(p) for p in pfade):
                self.entpreller.melden()


class Ordnerwaechter:
    """Startet und stoppt die Ueberwachung aller Ordner aus config.json.

    bei_aenderung() wird aus einem FREMDEN Thread aufgerufen (dem von
    watchdog). Wer darin Fensterinhalte aendern will, muss das selbst in
    den Hauptthread umleiten - siehe Hauptfenster.automatische_reindexierung.
    """

    def __init__(self, bei_aenderung):
        self._bei_aenderung = bei_aenderung
        self._entpreller = Entpreller(bei_aenderung)
        self._observer = None
        self._lock = threading.Lock()

    def _anhalten(self):
        """Nur mit gehaltenem Lock aufrufen."""
        self._entpreller.abbrechen()
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=2)
            except Exception:
                pass
            self._observer = None

    def neu_starten(self):
        """(Neu) starten - nach jeder Aenderung an der Ordnerliste aufrufen."""
        if not WATCHDOG_VERFUEGBAR:
            return
        with self._lock:
            self._anhalten()

            ordner_liste = lade_config().get("ordner", [])
            if not ordner_liste:
                return

            handler = OrdnerAenderungsHandler(self._entpreller)
            observer = Observer()

            ueberwachte = 0
            for o in ordner_liste:
                if os.path.exists(o):
                    observer.schedule(handler, path=o, recursive=True)
                    ueberwachte += 1

            if ueberwachte > 0:
                observer.start()
                self._observer = observer

    def stoppen(self):
        with self._lock:
            self._anhalten()
