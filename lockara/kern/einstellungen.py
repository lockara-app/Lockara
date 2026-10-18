#!/usr/bin/env python3
"""
einstellungen.py - alles, was sich Lockara ueber den Nutzer merkt:
ueberwachte Ordner, Sprache und Zaehler (config.json), Favoriten und
Suchverlauf. Dazu Export und Import der Einrichtung.

Die Dateien liegen im Datenordner des Systems, siehe pfade.py.
"""

import json
import os

from lockara.kern.pfade import CONFIG_FILE, FAVORITEN_FILE, VERLAUF_FILE


def _json_schreiben(pfad, daten):
    """Schreibt eine JSON-Datei atomar: erst in eine temporaere Datei, dann
    per os.replace() an ihren Platz - wie speichere_index() in index.py.

    Vorher wurde direkt in die Datei geschrieben. Stuerzt das Programm
    genau dabei ab (oder geht der Akku leer), bleibt eine halbe config.json
    liegen - und lade_config() scheiterte beim naechsten Start daran: die
    App liess sich nicht mehr oeffnen, bis jemand die Datei von Hand
    loeschte.

    Umlaute werden weiter als \\u-Folgen geschrieben (ensure_ascii): so
    liest auch eine aeltere Fassung die Datei, die unter Windows noch ohne
    Angabe der Codierung oeffnet - wichtig fuer ein Zurueckrollen.
    """
    temp_pfad = pfad + ".tmp"
    with open(temp_pfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, indent=2)
    os.replace(temp_pfad, pfad)


def _json_lesen(pfad, ersatz):
    """Liest eine JSON-Datei. Fehlt sie, kommt 'ersatz' zurueck. Ist sie
    kaputt, wird sie als <name>.defekt beiseitegelegt (nicht geloescht -
    vielleicht will jemand nachsehen) und ebenfalls 'ersatz' geliefert.
    Eine unlesbare Einstellungsdatei darf den Programmstart nie verhindern.

    Immer als UTF-8: unter Windows naehme open() sonst die Systemcodierung
    (cp1252), und eine von Hand bearbeitete Datei mit Umlauten kaeme
    verstuemmelt zurueck."""
    if not os.path.exists(pfad):
        return ersatz
    try:
        with open(pfad, encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, UnicodeDecodeError) as e:
        print(f"[Warnung] {os.path.basename(pfad)} ist beschaedigt und wird ersetzt: {e}")
        try:
            os.replace(pfad, pfad + ".defekt")
        except OSError:
            pass
        return ersatz


def lade_config():
    config = _json_lesen(CONFIG_FILE, {})
    if not isinstance(config, dict):
        config = {}
    # "ordner" muss immer eine Liste sein - ordner.py und
    # importiere_konfiguration() greifen ohne weitere Pruefung darauf zu.
    if not isinstance(config.get("ordner"), list):
        config["ordner"] = []
    return config


def speichere_config(config):
    _json_schreiben(CONFIG_FILE, config)


def automatische_updatepruefung():
    """Ob Lockara beim Start nach einer neuen Fassung fragt.

    Das ist die EINZIGE Verbindung, die das Programm von sich aus aufbaut
    (kern/updates.py: eine Anfrage an api.github.com, uebertragen werden
    nur IP-Adresse und Programmversion, nichts aus den Dateien). Kanzleien
    und ihre IT wollen das abschalten koennen - in den Einstellungen oder
    vorab per config.json: "update_pruefung": false. Ohne Eintrag: an."""
    return lade_config().get("update_pruefung", True) is not False


def setze_automatische_updatepruefung(an):
    config = lade_config()
    config["update_pruefung"] = bool(an)
    speichere_config(config)


def ueberwachte_ordner():
    """Aktuell in der config.json eingetragene Ordner, absolut."""
    return [
        os.path.abspath(os.path.expanduser(o))
        for o in lade_config().get("ordner", [])
    ]


# ---------- FAVORITEN ----------

def lade_favoriten():
    """Gibt die Menge der als Favorit markierten Dateipfade zurück."""
    try:
        favoriten = _json_lesen(FAVORITEN_FILE, [])
    except Exception as e:
        print(f"[Warnung] Favoriten konnten nicht geladen werden: {e}")
        return set()
    if not isinstance(favoriten, list):
        return set()
    return {p for p in favoriten if isinstance(p, str)}


def speichere_favoriten(favoriten):
    try:
        _json_schreiben(FAVORITEN_FILE, sorted(favoriten))
    except Exception as e:
        print(f"[Warnung] Favoriten konnten nicht gespeichert werden: {e}")


def favorit_umschalten(pfad):
    """Fügt pfad zu den Favoriten hinzu oder entfernt ihn.

    Gibt True zurück, wenn die Datei danach ein Favorit ist, sonst False.
    """
    favoriten = lade_favoriten()
    if pfad in favoriten:
        favoriten.remove(pfad)
        ist_favorit = False
    else:
        favoriten.add(pfad)
        ist_favorit = True
    speichere_favoriten(favoriten)
    return ist_favorit


# ---------- SUCHVERLAUF ----------

MAX_VERLAUF = 20


def lade_verlauf():
    """Die letzten Suchanfragen, neueste zuerst."""
    try:
        verlauf = _json_lesen(VERLAUF_FILE, [])
    except Exception:
        return []
    if not isinstance(verlauf, list):
        return []
    return [v for v in verlauf if isinstance(v, str)][:MAX_VERLAUF]


def speichere_verlauf(verlauf):
    try:
        _json_schreiben(VERLAUF_FILE, verlauf)
    except Exception:
        pass


def verlauf_ergaenzen(verlauf, anfrage):
    """Setzt die Anfrage an den Anfang (ohne Doppelungen, hoechstens
    MAX_VERLAUF Eintraege), speichert und gibt die neue Liste zurueck."""
    verlauf = [v for v in verlauf if v != anfrage]
    verlauf.insert(0, anfrage)
    verlauf = verlauf[:MAX_VERLAUF]
    speichere_verlauf(verlauf)
    return verlauf


def exportiere_konfiguration(zielpfad):
    """Schreibt überwachte Ordner + Favoriten als lesbare JSON-Datei.

    Praktisch als Backup oder um die eigene Einrichtung auf einen anderen
    Mac zu übertragen, ohne den kompletten (oft sehr großen) Suchindex
    mitnehmen zu müssen - der wird beim nächsten 'Index aktualisieren'
    einfach neu aufgebaut.
    """
    daten = {
        "ordner": lade_config().get("ordner", []),
        "favoriten": sorted(lade_favoriten()),
    }
    with open(zielpfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, indent=2, ensure_ascii=False)


def importiere_konfiguration(quellpfad):
    """Liest eine mit exportiere_konfiguration() erzeugte JSON-Datei ein
    und fügt überwachte Ordner + Favoriten zur bestehenden Einrichtung
    hinzu (überschreibt nichts, ergänzt nur). Gibt (anzahl_ordner,
    anzahl_favoriten) aus der importierten Datei zurück."""
    with open(quellpfad, "r", encoding="utf-8") as f:
        daten = json.load(f)

    importierte_ordner = daten.get("ordner", [])
    config = lade_config()
    for ordner in importierte_ordner:
        if ordner not in config["ordner"]:
            config["ordner"].append(ordner)
    speichere_config(config)

    importierte_favoriten = daten.get("favoriten", [])
    favoriten = lade_favoriten()
    favoriten.update(importierte_favoriten)
    speichere_favoriten(favoriten)

    return len(importierte_ordner), len(importierte_favoriten)
