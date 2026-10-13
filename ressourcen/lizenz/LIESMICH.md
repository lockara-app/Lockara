# Lizenzschlüssel

Hier liegt `oeffentlicher_schluessel.txt` – der öffentliche Schlüssel, mit dem SmartSearch Lizenzdateien prüft (`smartsearch/kern/lizenz.py`). Er ist nicht geheim und gehört ins Repository.

Angelegt wird er **einmal** auf dem Rechner, auf dem später auch die Lizenzen ausgestellt werden:

```
venv/bin/python -m werkzeuge.lizenz_ausstellen --schluessel-erzeugen
```

Dabei entsteht zusätzlich der **private** Schlüssel in `~/.smartsearch-lizenz/privat.key`. Der darf nie ins Repository und muss sicher aufbewahrt werden: Ohne ihn lassen sich keine Lizenzen mehr ausstellen, die bestehende Apps anerkennen.

Solange hier kein Schlüssel liegt, erkennt die App keine Lizenzdatei an (Status „ungültig“) – alles andere funktioniert normal.
