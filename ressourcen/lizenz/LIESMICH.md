# Lizenzschlüssel

Hier liegt `oeffentlicher_schluessel.txt` – der öffentliche Schlüssel, mit dem Lockara Lizenzdateien prüft (`lockara/kern/lizenz.py`). Er ist nicht geheim und gehört ins Repository.

Angelegt wird er **einmal** auf dem Rechner, auf dem später auch die Lizenzen ausgestellt werden:

```
venv/bin/python -m werkzeuge.lizenz_ausstellen --schluessel-erzeugen
```

Dabei entsteht zusätzlich der **private** Schlüssel in `~/.lockara-lizenz/privat.key`. Der darf nie ins Repository und muss sicher aufbewahrt werden: Ohne ihn lassen sich keine Lizenzen mehr ausstellen, die bestehende Apps anerkennen.

Solange hier kein Schlüssel liegt, erkennt die App keine Lizenzdatei an (Status „ungültig“) – alles andere funktioniert normal.

## Testlizenz auf Anfrage

Wer die Personensuche (DSGVO) ausprobieren will, klickt im gesperrten Fenster auf „Testlizenz per E-Mail anfragen“. Die Mail kommt an kontakt@lockara.de. Darauf:

```
venv/bin/python -m werkzeuge.lizenz_ausstellen --test --lizenznehmer "Kanzlei Muster"
```

Das gibt eine fertige Antwort-E-Mail mit dem **Lizenzcode** aus (beginnt mit `LOCKARA-`). Die Kanzlei fügt ihn im Fenster der Personensuche ein und klickt „Freischalten“. Die Testlizenz gilt 14 Tage (`lizenz.TEST_TAGE`), ohne Kulanz danach. Die normale Suche bleibt immer frei.

Auch Kauflizenzen lassen sich als Code verschicken: beim Ausstellen `--code` anhängen. Eingefügt wird der Code dann unter Einstellungen → Lizenz.
