#!/usr/bin/env python3
"""
nachsortierung.py - zweiter Blick auf die besten Kandidaten einer Suche.

WARUM ES DAS GIBT
-----------------
Das Suchmodell (kern/modell.py) rechnet jeden Text EINMAL in einen Vektor
um, die Anfrage ebenso, und vergleicht dann nur noch Vektoren. Das ist
schnell genug fuer tausende Dokumente, aber grob: Anfrage und Text sehen
sich nie gegenseitig. Gemessen am 50er-Testset (09.10.2026):

  - Bedeutungssuche 0 von 7. "Urlaub" findet die Reisebuchung nicht, weil
    zwei andere Dokumente das Wort "Urlaub" zufaellig enthalten.
  - Negativtests 1 von 4. Fuer "Gästeliste für die Hochzeit" liefert das
    Modell Werte um 0,79 - genauso hoch wie fuer echte Treffer. Eine feste
    Schwelle kann das nicht trennen.
  - 111 Fehlgriffe: Dokumente, die angezeigt werden, obwohl sie nicht
    dazugehoeren.

Ein Nachsortierer ("Cross-Encoder") liest Anfrage und Textabschnitt
GEMEINSAM und beurteilt, ob der Abschnitt die Anfrage beantwortet. Das ist
viel genauer, aber zu langsam fuer den ganzen Bestand - deshalb bekommt er
nur die besten Kandidaten der ersten Stufe (KANDIDATEN Dokumente, je
ABSCHNITTE_JE_DOKUMENT Abschnitte).

Sein Ergebnis ist eine Wahrscheinlichkeit zwischen 0 und 1, und die ist -
anders als die Vektor-Aehnlichkeit - ueber Anfragen hinweg vergleichbar.
Bei den vier Negativtests liegt sie unter 0,001, bei richtigen Treffern
fast immer deutlich darueber. Erst damit kann die Suche ehrlich sagen:
"Dazu habe ich nichts gefunden."

DAS MODELL
----------
BAAI/bge-reranker-v2-m3 - mehrsprachig (Deutsch/Englisch gemischt geht),
Apache-2.0, kommerziell ohne Auflagen nutzbar. Geladen als ONNX-Fassung
von onnx-community und von werkzeuge/modell_holen.py genauso verkleinert
wie das Suchmodell (Gewichte auf 8 Bit, gerechnet wird in voller
Genauigkeit). Ergebnis rund 640 MB. Auf den Testdokumenten liefert die
verkleinerte Fassung dieselbe Reihenfolge wie die volle.

OHNE MODELL GEHT ES AUCH
------------------------
Fehlen die Dateien, sucht die App wie vorher, nur mit der ersten Stufe.
Nichts bricht. So laesst sich die Nachsortierung jederzeit abschalten
(Ordner ressourcen/modell/bge-reranker-v2-m3 entfernen) und vergleichen.
"""

import os
import threading

from smartsearch.kern.pfade import ressource

MODELL_NAME = "BAAI/bge-reranker-v2-m3"
# Herkunft der ONNX-Fassung (dieselben Gewichte, nur exportiert).
ONNX_QUELLE = "onnx-community/bge-reranker-v2-m3-ONNX"

MODELL_ORDNER = "modell/bge-reranker-v2-m3"
MODELL_DATEI = "onnx/model_smartsearch_int8.onnx"
QUELL_DATEI = "onnx/model.onnx"
QUELL_DATEN = "onnx/model.onnx_data"   # die Gewichte des grossen Modells
TOKENIZER_DATEI = "tokenizer.json"

AUSLIEFERN = [TOKENIZER_DATEI, "config.json", "LIZENZ.txt", "PRUEFSUMMEN.txt", MODELL_DATEI]

# Nur fuer Messungen: Nachsortierung abschalten, ohne Dateien zu loeschen.
ABGESCHALTET = os.environ.get("SMARTSEARCH_OHNE_NACHSORTIERUNG") == "1"

# ---------------------------------------------------------------------------
# Einstellungen - gemessen mit werkzeuge/such_diagnose.py (09.10.2026).
#
# Gerastert wurden Schwelle (0,0005-0,01), Abstand (0,05-0,7), Kandidaten
# und drei Arten, beide Stufen zu verrechnen. Ueber eine breite Spanne um
# die Werte unten liegt das Ergebnis bei 55-59 von 69 richtig mit 13-17
# Fehlgriffen (ohne Nachsortierung: 48-50 richtig, 110 Fehlgriffe).
# Gemessen in der Cloud mit Tesseract als Texterkennung; auf dem Mac
# (Apple Vision) koennen die Scan-Faelle anders ausfallen.
# ---------------------------------------------------------------------------

# Wie viele Dokumente der ersten Stufe der Nachsortierer liest, und je
# Dokument wie viele Abschnitte (die mit der hoechsten Vektor-Aehnlichkeit).
# Die Rechenzeit waechst mit Kandidaten x Abschnitten. Gemessen:
#     6 x 2: 59 richtig     8 x 2: 58     14 x 2: 58
#     8 x 1: 51             14 x 1: 51
# Der zweite Abschnitt je Dokument zaehlt also viel, weitere Kandidaten
# kaum. 8 x 2 = 16 Abschnitte je Suche laesst Luft fuer groessere
# Bestaende, in denen das Richtige seltener ganz vorn in der ersten Stufe
# steht.
KANDIDATEN = 8
ABSCHNITTE_JE_DOKUMENT = 2

# Ein Abschnitt ist hoechstens 350 Zeichen lang (dateien.py), zusammen mit
# der Anfrage also weit unter dieser Grenze. Sie schuetzt nur vor
# ueberlangen Anfragen.
MAX_TOKEN = 384

# Liegt selbst der beste Kandidat darunter, gibt es zu dieser Anfrage
# nichts im Bestand. Negativtests: alle unter 0,001. Richtige Treffer:
# bis auf Ausnahmen ueber 0,005.
MINDEST_WAHRSCHEINLICHKEIT = 0.002

# Angezeigt wird, was mindestens diesen Anteil der Wahrscheinlichkeit des
# besten Kandidaten erreicht. Die Wahrscheinlichkeiten fallen steil ab -
# ein Dokument mit einem Drittel des besten Werts ist meist noch passend,
# eines mit einem Zehntel fast nie.
RELATIVER_ABSTAND = 0.3

# Die Reihenfolge entsteht aus BEIDEN Stufen ("Reciprocal Rank Fusion"):
# Rang beim Nachsortierer und Rang in der ersten Stufe, gleich gewichtet.
# Die erste Stufe kennt die woertlichen Treffer (Aktenzeichen, Namen,
# Dateinamen), der Nachsortierer die Bedeutung. Allein nach dem
# Nachsortierer sortiert: 54 statt 57 richtig.
RRF_K = 10
GEWICHT_ERSTE_STUFE = 1.0

STAPEL = 8


def modell_pfad(datei=""):
    return ressource(os.path.join(MODELL_ORDNER, datei)) if datei else ressource(MODELL_ORDNER)


def ist_vorhanden():
    return (not ABGESCHALTET
            and os.path.isfile(modell_pfad(MODELL_DATEI))
            and os.path.isfile(modell_pfad(TOKENIZER_DATEI)))


class Nachsortierer:
    def __init__(self, modell_datei, tokenizer_datei):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.tokenizer = Tokenizer.from_file(tokenizer_datei)
        self.tokenizer.enable_truncation(max_length=MAX_TOKEN)
        if self.tokenizer.padding is None:
            self.tokenizer.enable_padding()
        self.sitzung = ort.InferenceSession(
            modell_datei, sess_options=ort.SessionOptions(),
            providers=["CPUExecutionProvider"])
        self._eingaenge = {e.name for e in self.sitzung.get_inputs()}
        # Eine Sitzung darf von mehreren Threads benutzt werden, aber zwei
        # gleichzeitige Suchen wuerden sich nur gegenseitig ausbremsen.
        self._sperre = threading.Lock()

    def wahrscheinlichkeiten(self, anfrage, texte):
        """Fuer jeden Text: wie wahrscheinlich beantwortet er die Anfrage
        (0 bis 1)."""
        import numpy as np

        # Nach Laenge sortiert rechnen: in einem Stapel wird jeder Text auf
        # den laengsten aufgefuellt, aehnlich lange Texte sparen Rechenzeit.
        reihenfolge = sorted(range(len(texte)), key=lambda i: len(texte[i]))
        sortiert = [texte[i] for i in reihenfolge]
        werte = []
        with self._sperre:
            for i in range(0, len(sortiert), STAPEL):
                teil = sortiert[i:i + STAPEL]
                kodiert = self.tokenizer.encode_batch([(anfrage, t) for t in teil])
                eingabe = {
                    "input_ids": np.asarray([k.ids for k in kodiert], dtype="int64"),
                    "attention_mask": np.asarray([k.attention_mask for k in kodiert], dtype="int64"),
                }
                eingabe = {k: v for k, v in eingabe.items() if k in self._eingaenge}
                logits = self.sitzung.run(None, eingabe)[0].reshape(len(teil), -1)[:, 0]
                werte.extend((1.0 / (1.0 + np.exp(-logits))).tolist())
        ergebnis = [0.0] * len(texte)
        for stelle, wert in zip(reihenfolge, werte):
            ergebnis[stelle] = wert
        return ergebnis


_cache = None
_cache_lock = threading.Lock()
_fehlgeschlagen = False


def geladener_nachsortierer():
    """Der Nachsortierer, einmal geladen - oder None, wenn er fehlt oder
    sich nicht laden laesst. Die Suche laeuft dann ohne ihn weiter."""
    global _cache, _fehlgeschlagen
    if _cache is not None or _fehlgeschlagen:
        return _cache
    if not ist_vorhanden():
        return None
    with _cache_lock:
        if _cache is None and not _fehlgeschlagen:
            try:
                print(f"Lade Nachsortierer ({MODELL_NAME})...")
                _cache = Nachsortierer(modell_pfad(MODELL_DATEI), modell_pfad(TOKENIZER_DATEI))
            except Exception as e:
                # Nicht bei jeder Suche erneut versuchen und scheitern.
                _fehlgeschlagen = True
                print(f"[Nachsortierung] nicht verfuegbar: {e}")
    return _cache
