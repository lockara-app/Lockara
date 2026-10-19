# Aufbau von Lockara

Stand: 18.10.2026, Fassung 1.1.0.

## Die drei Schichten

```
   oberflaeche/   zeigt an, reagiert auf Klicks
        │
        ▼
      kern/       rechnet, liest, speichert – kennt keine Fenster
        │
        ▼
   plattform/     spricht mit dem Betriebssystem
```

Pfeile bedeuten: *darf importieren*. Umgekehrt nie.

- **`kern/` importiert nichts aus `oberflaeche/`.** Kein `customtkinter`, kein `messagebox`, kein `t("...")`. Der Kern gibt Zahlen, Listen und Ausnahmen zurück. Formulieren und Anzeigen ist Sache der Oberfläche.
  - Beispiel: `indexierung.alles_indexieren()` meldet `{"art": "datei", "n": 3, "gesamt": 120, "restzeit_sek": 95}`. Das Hauptfenster macht daraus „Indexiere 3 von 120 … noch etwa 2 Min“.
- **`oberflaeche/` rechnet nicht.** Liest oder schreibt eine Methode Dateien oder bewertet etwas, gehört sie in den Kern.
- **`plattform/` hat drei Dateien mit denselben Funktionsnamen:** `mac.py`, `windows.py` und `andere.py`. `plattform/__init__.py` lädt beim Start die passende. Im restlichen Code steht deshalb nirgends „wenn Mac, dann …“.

### Warum so streng

In einem früheren Projekt des Kollegen hat eine Java-Klasse Rechnen, Kollisionen, Zeichnen und das Erzeugen von Objekten gleichzeitig erledigt. Die 1.000 Zeilen später auseinanderzunehmen hat Tage gekostet.

Lockara stand kurz davor: `gui.py` hatte 3.000 Zeilen in **einer** Klasse. Darin steckten Indexlauf, Updateprüfung, Ordnerüberwachung, Einzelinstanz, Rückmeldung, Suchverlauf und alle Dialoge. Das hätte zwei konkrete Folgen gehabt:

1. **Umstieg auf PySide6:** Die Logik hätte man aus dem Oberflächencode herausoperieren müssen. Jetzt bleibt `kern/` beim Umstieg unangetastet, neu geschrieben wird nur `oberflaeche/`.
2. **Zwei Leute, eine Datei:** Mac- und Windows-Arbeit hätten sich ständig in derselben Datei überschnitten. Jetzt arbeitet jeder überwiegend in seiner eigenen `plattform/`-Datei.

## Mac und Windows: was gleich ist, was nicht

| Gleich auf beiden Systemen | Verschieden (nur in `plattform/` und `bauen/`) |
|---|---|
| Suche, Bewertung, Wortformen (`kern/suche.py`, `kern/sprache.py`) | Datei öffnen, im Finder/Explorer zeigen, Vorschau |
| Suchmodell, Nachsortierer, Indexformat (`kern/modell.py`, `kern/nachsortierung.py`, `kern/index.py`) | Benachrichtigung, Autostart, Systemsprache |
| Dateien lesen (`kern/dateien.py`) | Symbol in Menüleiste bzw. Infobereich, Tastenkürzel, Dock/Taskleiste |
| Oberfläche, Texte, Farben (`oberflaeche/`) | Datenordner (`~/Library/Application Support` bzw. `%LOCALAPPDATA%`, in `kern/pfade.py`) |
| Einstellungen, Favoriten, Verlauf, Updates | Paket: `.app`/DMG bzw. `.exe`/MSI (`bauen/`) |
| Versionsnummer (`version.py`) | Signieren: Apple-Konto bzw. Windows-Zertifikat |

**Texterkennung:** `kern/ocr.py` nutzt auf allen Systemen RapidOCR, damit derselbe Scan überall denselben Text und denselben Index ergibt. Apple Vision (Mac) und Tesseract (Windows) bleiben nur als Ausweichweg, falls RapidOCR fehlt.

## Regeln für neue Funktionen

- **Neue Systemfunktion:** In `mac.py`, `windows.py` **und** `andere.py` anlegen (notfalls als „tut nichts“) und in `plattform/__init__.py` in die Liste eintragen.
- **Neuer sichtbarer Text:** Kommt in `oberflaeche/i18n.py`, auf Deutsch **und** Englisch. Im Kern stehen keine Sätze für Nutzer.
- **Neue Datei im Datenordner:** Den Pfad in `kern/pfade.py` festlegen, nirgends sonst.
- **Neues Symbol oder Bild:** Nach `ressourcen/`, geladen über `pfade.ressource("icons/…")`. Nur so findet die gebaute App es.
- **Neuer Dialog:** Eine eigene Datei in `oberflaeche/dialoge/` mit einer Funktion, die das Hauptfenster als `app` bekommt.
- **Versionsnummer:** Nur `lockara/version.py`. Die Specs und `build.sh` lesen sie von dort.

## Bekannte Baustellen

- `oberflaeche/hauptfenster.py` hat noch rund 1.500 Zeilen: Aufbau des Fensters, Seitenleiste, Suche, Fensterverhalten. Sie wird beim Umstieg auf PySide6 ohnehin neu geschrieben und dabei in Fenster und Seitenleiste aufgeteilt. Vorher lohnt sich das Zerlegen nicht.

## Regeln für Dateien im Datenordner

- **Immer atomar schreiben:** erst in `<datei>.tmp`, dann `os.replace()`. So bleibt bei einem Absturz mitten im Schreiben nie eine halbe Datei liegen (`kern/einstellungen.py`, `kern/index.py`).
- **Eine Datei kommt nur ganz in den Index:** mit allen Abschnitten samt Vektor oder als „ohne Inhalt“ (`indexierung._zwischenstand`). Sonst gilt eine halb eingelesene Datei beim nächsten Lauf als erledigt.
- **Kaputte Einstellungen verhindern nie den Start:** `lade_config()` legt eine unlesbare Datei als `.defekt` beiseite und macht mit leeren Einstellungen weiter.
- **Den Index nie im Tk-Hauptthread lesen:** er kann mehrere hundert MB groß sein. Ergebnisse gehen über `self.after(0, …)` zurück ins Fenster.

Geprüft wird das in `tests/test_robustheit.py`.
