# Lockara

Lokale Dateisuche für Mac und Windows: findet Dokumente nach ihrem **Inhalt**, nicht nach dem Dateinamen. Alles läuft auf dem eigenen Rechner, ohne Konto und ohne Cloud.

Website: [lockara.de](https://lockara.de). Die Website selbst liegt **nicht** in diesem Repository.

## Einrichten

Es braucht **Python 3.13**. Warum genau diese Fassung, steht in `requirements.txt`.

**Mac**

```
python3.13 -m venv venv
venv/bin/python -m pip install -r requirements.txt
```

**Windows**

```
py -3.13 -m venv venv
venv\Scripts\python -m pip install -r requirements.txt
```

Danach einmal die beiden Modelle holen: das Suchmodell und den Nachsortierer. Sie liegen nicht im Repository; geladen werden rund 2,7 GB, daraus entstehen die verkleinerten Fassungen, die in die App kommen (zusammen rund 740 MB):

```
venv/bin/python -m werkzeuge.modell_holen
```

Unter Windows `venv\Scripts\python -m werkzeuge.modell_holen`. Die fertige App bringt das Modell mit, Nutzer laden nichts herunter.

## Starten

Immer im Projektordner:

| | Mac | Windows |
|---|---|---|
| Programm | `venv/bin/python -m lockara` | `venv\Scripts\python -m lockara` |
| Wortformen-Test (1 Sekunde) | `venv/bin/python -m tests.test_wortformen` | `venv\Scripts\python -m tests.test_wortformen` |
| Begriffsliste-Test (1 Sekunde) | `venv/bin/python -m tests.test_begriffe` | `venv\Scripts\python -m tests.test_begriffe` |
| Robustheitstest (1 Sekunde) | `venv/bin/python -m tests.test_robustheit` | `venv\Scripts\python -m tests.test_robustheit` |
| Rolltest (1 Sekunde) | `venv/bin/python -m tests.test_rollen` | `venv\Scripts\python -m tests.test_rollen` |
| Personensuche-Test (1 Sekunde) | `venv/bin/python -m tests.test_personensuche` | `venv\Scripts\python -m tests.test_personensuche` |
| Personensuche messen (50 Testakten) | `venv/bin/python -m werkzeuge.personensuche_messen` | `venv\Scripts\python -m werkzeuge.personensuche_messen` |
| Personen-Testakten neu erzeugen | `venv/bin/python -m werkzeuge.testdokumente.personen` | `venv\Scripts\python -m werkzeuge.testdokumente.personen` |
| Suchqualität messen | `venv/bin/python -m werkzeuge.such_diagnose --testdokumente` | `venv\Scripts\python -m werkzeuge.such_diagnose --testdokumente` |
| Testdokumente neu erzeugen | `venv/bin/python -m werkzeuge.testdokumente` | `venv\Scripts\python -m werkzeuge.testdokumente` |
| Index untersuchen | `venv/bin/python -m werkzeuge.diagnose` | `venv\Scripts\python -m werkzeuge.diagnose` |
| Lizenz-Test (1 Sekunde) | `venv/bin/python -m tests.test_lizenz` | `venv\Scripts\python -m tests.test_lizenz` |
| Lizenz ausstellen | `venv/bin/python -m werkzeuge.lizenz_ausstellen --help` (siehe `ressourcen/lizenz/LIESMICH.md`) | entsprechend |

Wichtig ist das `-m`. `python lockara/start.py` oder `python tests/test_wortformen.py` findet die eigenen Module nicht.

## Wo was liegt

```
lockara/              das Programm
├── __main__.py           Startpunkt
├── start.py              Programmstart, nur eine laufende Kopie, Selbsttest
├── version.py            die Versionsnummer, an genau einer Stelle
├── kern/                 GEMEINSAM für alle Systeme, ohne Oberfläche
│   ├── suche.py            Anfrage bewerten, ähnliche Dokumente
│   ├── sprache.py          Suchwörter, deutsche Wortformen, Fundstellen
│   ├── index.py            index.pkl lesen/schreiben/aufräumen
│   ├── indexierung.py      Dateien einlesen, kompletter Indexlauf
│   ├── modell.py           Suchmodell (ONNX) laden
│   ├── nachsortierung.py   zweite Stufe: beste Kandidaten genauer prüfen
│   ├── dateien.py          Dateien finden, Text auslesen
│   ├── ocr.py              Texterkennung für Scans
│   ├── einstellungen.py    config.json, Favoriten, Suchverlauf
│   ├── ordner.py           Ordner hinzufügen/entfernen
│   ├── ueberwachung.py     Ordner beobachten (watchdog)
│   ├── updates.py          neue Fassung auf GitHub?
│   ├── rueckmeldung.py     Bitte um Rückmeldung, E-Mail-Text
│   ├── einzelinstanz.py    nur eine laufende Kopie
│   └── pfade.py            wo Daten und Symbole liegen
├── oberflaeche/          GEMEINSAM: Fenster, Texte, Farben
│   ├── hauptfenster.py
│   ├── trefferkarte.py
│   ├── dialoge/            Einstellungen, Einführung, Ordner, Fehlerliste, Hinweise
│   ├── i18n.py             alle Texte, Deutsch und Englisch
│   └── farben.py
└── plattform/            UNTERSCHIEDLICH je System
    ├── mac.py
    ├── windows.py
    └── andere.py           nur zum Testen unter Linux
ressourcen/icons/         Programmsymbole
bauen/mac/                Spec, build.sh, Doppelklick-Helfer
bauen/windows/            Spec (später WiX-Installer)
werkzeuge/                Diagnose-Skripte
tests/                    Tests, 50 Testdokumente, Soll-Antworten (suchfaelle.py)
docs/                     ARCHITEKTUR.md, RELEASE.md, TESTANLEITUNG.md
```

Wie die Teile zusammenhängen und welche Regeln gelten, steht in [docs/ARCHITEKTUR.md](docs/ARCHITEKTUR.md).

## Zusammenarbeit

Marcel arbeitet am Mac-Teil, sein Kollege am Windows-Teil. Beide arbeiten im selben Repository und am selben Code.

1. `main` ist immer lauffähig. Direkt auf `main` wird nicht gearbeitet.
2. Für jede Aufgabe gibt es einen eigenen, kurzen Zweig:
   ```
   git switch main
   git pull
   git switch -c windows-infobereich
   ```
3. Arbeiten, committen und hochladen:
   ```
   git push -u origin windows-infobereich
   ```
4. Auf GitHub einen **Pull Request** nach `main` stellen. Der andere schaut kurz drüber, dann wird zusammengeführt.
5. Danach bei beiden: `git switch main && git pull`.

Was jeder anfasst:

| Arbeit an … | Dateien |
|---|---|
| Windows | `lockara/plattform/windows.py`, `bauen/windows/` |
| Mac | `lockara/plattform/mac.py`, `bauen/mac/` |
| beide Systeme | `lockara/kern/`, `lockara/oberflaeche/` |

Bei den gemeinsamen Dateien vorher kurz absprechen, wer woran sitzt.

### Automatische Tests

Jeder Pull Request wird auf GitHub automatisch geprüft (`.github/workflows/tests.yml`, sichtbar unter „Checks“):

- **Schnelltests** auf Mac, Windows und Linux: Pakete installieren, alle Dateien übersetzen, Wortformen-, Lizenz-, Begriffsliste-, Roll- und Robustheitstest.
- **Suchqualität** unter Linux: die Suchdiagnose mit den 50 Testdokumenten. Fällt das Ergebnis unter die Werte in `tests/mindestwerte.json`, wird der Pull Request rot. Lokal: `venv/bin/python -m werkzeuge.ci_pruefen`.

Wird die Suche besser, die Werte in `tests/mindestwerte.json` nachziehen.

Wie eine neue Fassung herausgegeben wird, steht in [docs/RELEASE.md](docs/RELEASE.md).
