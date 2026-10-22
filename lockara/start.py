#!/usr/bin/env python3
"""
start.py - der Programmstart: Selbsttest, nur eine laufende Kopie,
Hauptfenster, Symbol in Menueleiste bzw. Infobereich.

Aufgerufen von lockara/__main__.py (Quelltext: venv/bin/python -m
lockara; in der gebauten App der Einstiegspunkt von PyInstaller).
"""

import os
import sys
import time

from lockara import plattform
from lockara.kern import einzelinstanz
from lockara.kern.pfade import DATEN_ORDNER, ressource


def selbsttest():
    """Prueft im fertigen Bundle, ob sich alle noetigen Bausteine
    tatsaechlich importieren lassen, und beendet sich dann wieder.

    Der Anlass: eine ausgelieferte Fassung startete einwandfrei, scheiterte
    aber auf einem frisch aufgesetzten Mac beim Laden des Suchmodells an
    einem fehlenden Modul ('torchgen'). Die bisherige Pruefung suchte nur
    nach Zeichenketten im Archiv - das faellt bei einem Paket, das
    zusaetzliche Datendateien braucht, nicht auf. Hier wird stattdessen
    wirklich importiert, in genau der Umgebung, die spaeter auch beim
    Nutzer laeuft.
    """
    pflicht = [
        "onnxruntime", "tokenizers", "numpy", "customtkinter",
    ]
    optional = {
        "pdfplumber": "PDF (Haupterkennung)",
        "pypdf": "PDF (Ausweichweg)",
        "docx": "Word",
        "openpyxl": "Excel",
        "pptx": "PowerPoint",
        "pypdfium2": "Seiten fuer Texterkennung",
        "rapidocr": "Texterkennung (RapidOCR)",
        "Vision": "Texterkennung",
        "watchdog": "Automatische Aktualisierung",
        "cryptography": "Lizenzpruefung",
        "langchain_text_splitters": "Aufteilung in Abschnitte",
    }

    import importlib
    fehler = 0

    print("Zwingend erforderlich:")
    for name in pflicht:
        try:
            importlib.import_module(name)
            print(f"  ok      {name}")
        except Exception as e:
            print(f"  FEHLT   {name}: {e}")
            fehler += 1

    print("\nJe Dateiformat:")
    for name, zweck in optional.items():
        try:
            importlib.import_module(name)
            print(f"  ok      {name:26s} {zweck}")
        except Exception as e:
            print(f"  FEHLT   {name:26s} {zweck}  ({e})")
            fehler += 1

    # Nicht nur die Module - das mitgelieferte Modell wird wirklich geladen
    # und rechnet einen Probesatz. Genau so, wie es spaeter beim Nutzer
    # laeuft. (Frueher scheiterte eine Fassung erst auf einem fremden Mac
    # beim Laden des Modells, obwohl alle Module da waren.)
    print("\nSuchmodell:")
    try:
        from lockara.kern import modell
        vektor = modell.lade_modell().encode(["Probesatz fuer den Selbsttest"])
        print(f"  ok      {modell.MODELL_NAME} ({modell.MODELL_DATEI}), {vektor.shape[1]} Werte je Text")
    except Exception as e:
        print(f"  FEHLT   {e}")
        fehler += 1

    # Der PDF-Bericht der Personensuche: reportlab wird erst beim Speichern
    # geladen und zieht Teile ueber Namen nach - ob das im Bundle klappt,
    # zeigt nur ein echter Bericht. Geschrieben wird in einen Temp-Ordner.
    print("\nBericht der Personensuche:")
    try:
        import datetime
        import tempfile
        from lockara import plattform as pf
        from lockara.kern import bericht, personensuche as ps
        person = ps.Person(name="Selbst Test")
        ergebnis = ps.Ergebnis(person, [], 0, [], [], datetime.datetime.now(), None)
        texte = {k: k for k in bericht.TEXT_SCHLUESSEL}
        texte["datum_format"] = "%d.%m.%Y"
        ziel = os.path.join(tempfile.mkdtemp(prefix="lockara-selbsttest-"), "bericht.pdf")
        bericht.schreiben(ziel, ergebnis, texte, {m: m for m in ps.MERKMAL_REIHENFOLGE}, "selbsttest")
        schrift = "Systemschrift" if pf.schriftdateien() else "Helvetica (Ausweichschrift)"
        print(f"  ok      PDF geschrieben ({os.path.getsize(ziel)} Bytes, {schrift})")
    except Exception as e:
        print(f"  FEHLT   {e}")
        fehler += 1

    print()
    if fehler:
        print(f"Ergebnis: {fehler} Baustein(e) fehlen. Das Bundle ist unbrauchbar.")
    else:
        print("Ergebnis: vollstaendig.")
    sys.exit(1 if fehler else 0)


def bereits_offene_instanz_aktivieren():
    """Sorgt dafuer, dass Lockara hoechstens einmal laeuft.

    Warum das noetig ist: Auf einem Mac koennen problemlos zwei Kopien
    derselben Anwendung gleichzeitig laufen - eine aus dem
    Programme-Ordner, eine aus einem Bau- oder Testordner. Beide heissen
    Lockara, beide legen ein Symbol in der Menueleiste an, und beide
    greifen auf denselben Index zu. Fuer den Benutzer sieht das aus, als
    haette sich das Programm von selbst ein zweites Mal geoeffnet.

    Ist bereits eine Instanz da, wird sie nach vorne geholt und diese hier
    beendet sich sofort - dasselbe Verhalten, das man von jeder anderen
    Mac-Anwendung kennt.

    Rueckgabe: True, wenn sich dieser Start beenden soll.
    """
    # 1. Der saubere Weg ueber das Betriebssystem: macOS fuehrt Buch
    #    darueber, welche Anwendungen mit welcher Bundle-Kennung laufen.
    #    Das erfasst auch eine zweite Kopie an einem anderen Ort.
    if plattform.SYMBOL_VERFUEGBAR:
        # Reihenfolge wichtig: erst das Signal legen, dann die laufende
        # Kopie nach vorne holen - so ist ihr Fenster schon auf dem Weg,
        # wenn sie aktiviert wird.
        einzelinstanz.bitte_fenster_zeigen()
        if plattform.laufende_instanz_aktivieren():
            print("[Start] Lockara laeuft bereits - vorhandenes Fenster geholt.")
            return True
        # Es lief doch keine zweite Kopie: das eben gelegte Signal wieder
        # wegraeumen, damit sich dieses Fenster nicht gleich beim eigenen
        # Start selbst "von aussen" anstupst.
        einzelinstanz.zeigen_signal_verwerfen()

    # 2. Ausweichweg fuer den Fall, dass die Anwendung ohne Bundle
    #    gestartet wurde (direkt aus dem Quelltext) - dann kennt macOS
    #    keine Bundle-Kennung.
    return einzelinstanz.andere_kopie_ueber_sperrdatei()


def _start_protokollieren():
    """Schreibt eine Zeile pro Programmstart nach start_log.txt.

    Reine Diagnosehilfe: taucht ein zweites Dock-Symbol auf, steht hier
    schwarz auf weiss, ob wirklich ein zweiter Prozess gestartet wurde
    (zwei Zeilen mit unterschiedlicher Prozessnummer im selben Moment)
    oder ob macOS nur zweimal dasselbe Programm anzeigt. Die Datei bleibt
    klein - es werden nur die letzten 50 Zeilen aufgehoben.
    """
    try:
        os.makedirs(DATEN_ORDNER, exist_ok=True)
        pfad = os.path.join(DATEN_ORDNER, "start_log.txt")
        zeile = "%s  PID %s  Elternprozess %s  argv=%s\n" % (
            time.strftime("%Y-%m-%d %H:%M:%S"), os.getpid(), os.getppid(), sys.argv)
        zeilen = []
        if os.path.exists(pfad):
            with open(pfad, encoding="utf-8", errors="replace") as f:
                zeilen = f.readlines()[-49:]
        with open(pfad, "w", encoding="utf-8") as f:
            f.writelines(zeilen)
            f.write(zeile)
    except Exception as e:
        print(f"[Start] Startprotokoll nicht moeglich: {e}")


def starten():
    _start_protokollieren()

    if "--selbsttest" in sys.argv:
        selbsttest()

    if bereits_offene_instanz_aktivieren():
        sys.exit(0)

    # Bis 1.0.8 hiess das Programm SmartSearch. Datenordner und Lizenz zieht
    # pfade.py bzw. lizenz.py um; hier noch der Autostart.
    plattform.fruehere_einstellungen_uebernehmen()

    # Muss VOR dem ersten Fenster stehen: Tk liest den Programmnamen fuer
    # das Anwendungsmenue genau einmal, beim Aufbau des Fensters.
    if plattform.SYMBOL_VERFUEGBAR:
        plattform.programmnamen_setzen("Lockara")

    # numpy einmal hier im Hauptthread laden, BEVOR Hintergrund-Threads
    # starten. Sonst laden beim Start zwei Threads numpy gleichzeitig (das
    # Vorladen des Suchmodells und das Lesen des Index - pickle braucht
    # numpy fuer die Vektoren). Python bricht einen der beiden Importe dann
    # mit "deadlock detected by _ModuleLock" ab, der Index galt als
    # unlesbar, und Lockara baute ihn ohne Not komplett neu auf - mit
    # der irrefuehrenden Meldung, das Suchmodell habe sich geaendert.
    # Gefunden am 13.10.2026 beim Testen.
    import numpy  # noqa: F401

    # Erst hier importiert: die Oberflaeche zieht customtkinter und das
    # Farbthema nach sich. Fuer --selbsttest und eine zweite Kopie, die
    # sich gleich wieder beendet, ist das unnoetig.
    from lockara.oberflaeche.hauptfenster import Hauptfenster

    app_window = Hauptfenster()

    status_handler = None
    if plattform.SYMBOL_VERFUEGBAR:
        # Symbol in der Menueleiste (Mac) bzw. im Infobereich (Windows).
        # Das Ergebnis MUSS in einer Variablen bleiben, sonst raeumt Python
        # das Objekt weg und das Symbol verschwindet wieder.
        status_handler = plattform.menueleisten_symbol_anlegen(
            lambda: setattr(app_window, "toggle_requested", True),
            beenden_callback=lambda: setattr(app_window, "beenden_requested", True),
            icon_pfad=ressource("icons/icon.png"),
        )
        plattform.als_programm_im_dock_anmelden()
        plattform.dock_symbol_setzen(ressource("icons/icon.png"))

    if plattform.IST_WINDOWS:
        # Fenster- und Taskleistensymbol setzt unter Windows Tkinter selbst,
        # dafuer braucht es die .ico-Datei (.png versteht Windows an dieser
        # Stelle nicht).
        try:
            app_window.iconbitmap(ressource("icons/icon.ico"))
        except Exception as e:
            print(f"[Icon] Fenstersymbol konnte nicht gesetzt werden: {e}")

    app_window.mainloop()
    return status_handler
