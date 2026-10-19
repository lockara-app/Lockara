#!/usr/bin/env python3
"""
indexierung.py - Dateien einlesen und in den Index aufnehmen.

aktualisiere_index() arbeitet EINEN Ordner ab (nur neue und geaenderte
Dateien). alles_indexieren() ist der komplette Lauf ueber alle
ueberwachten Ordner, wie ihn die Oberflaeche anstoesst - mit Modell-
Download, Fortschritt, Restzeit, Abbruch und anschliessendem Aufraeumen.
Die Oberflaeche zeigt nur noch an, was hier gemeldet wird.
"""

import math
import os
import time
from concurrent.futures import ThreadPoolExecutor

from lockara.kern.dateien import dateien_im_ordner, in_abschnitte_teilen, leser_stand, lies_datei
from lockara.kern.index import bereinige_index, lade_bestehenden_index, speichere_index
from lockara.kern.modell import geladenes_modell

# Anzahl paralleler Threads beim Einlesen der Dateien (Text-Extraktion/OCR).
# Diese Arbeit ist größtenteils I/O bzw. läuft in C-Bibliotheken
# (pdfplumber, Tesseract), die während der Arbeit die Python-GIL freigeben -
# paralleles Lesen bringt hier also einen echten Geschwindigkeitsgewinn,
# unabhängig vom CPU-Modus des KI-Modells (siehe lade_modell()).
LESE_THREADS = 4


def _geaendert_am(pfad):
    """Zeitstempel der letzten Aenderung - oder None, wenn die Datei
    inzwischen weg ist.

    Zwischen dem Durchsuchen des Ordners und dem Einlesen vergehen bei
    grossen Ordnern Minuten. Wird in der Zeit eine Datei geloescht oder
    verschoben (ein Download, der umbenannt wird, eine Word-Sicherung),
    warf os.path.getmtime() einen Fehler - und brach den GESAMTEN Indexlauf
    ab, mit "Fehler bei der Indexierung" in der Statuszeile."""
    try:
        return os.path.getmtime(pfad)
    except OSError:
        return None


def _muss_gelesen_werden(pfad, bekannt, gelesen_mit):
    if pfad not in bekannt or gelesen_mit.get(pfad, 1) < leser_stand(pfad):
        return True
    geaendert = _geaendert_am(pfad)
    return geaendert is not None and geaendert > bekannt[pfad]


def _zwischenstand(neue_eintraege, alte_eintraege):
    """Die Eintraege, die jetzt schon in den Index duerfen.

    Eine Datei kommt nur GANZ hinein - mit allen Abschnitten samt Vektor
    oder als "ohne Inhalt". Frueher wurde abschnittsweise gespeichert: Wurde
    das Programm zwischen zwei Zwischenspeicherungen beendet, stand eine
    Datei mit der Haelfte ihrer Abschnitte im Index, galt beim naechsten Lauf
    als erledigt (der Zeitstempel stimmte ja) und blieb fuer immer nur halb
    durchsuchbar.

    Fuer Dateien, die noch nicht fertig sind, bleiben die alten Eintraege
    stehen. Sie tragen den alten Zeitstempel, also liest der naechste Lauf
    die Datei ohnehin neu, falls dieser hier nicht zu Ende kommt.
    """
    unfertig = {e["datei"] for e in neue_eintraege
                if not e.get("ohne_inhalt") and "vektor" not in e}
    fertig = [e for e in neue_eintraege if e["datei"] not in unfertig]
    fertige_dateien = {e["datei"] for e in fertig}
    noch_alt = [e for pfad, liste in alte_eintraege.items()
                if pfad not in fertige_dateien for e in liste]
    return fertig + noch_alt


def aktualisiere_index(ordner, modell=None, still=False, fortschritt_fn=None,
                       soll_abbrechen=None, dateien=None, geplant_fn=None):
    """Bringt den Index fuer EINEN Ordner auf den neuesten Stand.

    soll_abbrechen: wie bei alles_indexieren(). Wird jetzt auch MITTEN im
    Ordner abgefragt - vorher erst zwischen zwei Ordnern. Wer einen
    einzigen grossen Ordner eingetragen hatte (der Normalfall), konnte den
    Lauf mit "Abbrechen" also gar nicht anhalten. Was bis dahin fertig
    ist, bleibt im Index; der Rest kommt beim naechsten Lauf.
    dateien: die Dateien des Ordners, wenn der Aufrufer sie schon kennt -
    alles_indexieren() hat sie zum Zaehlen ohnehin gesammelt, und ein
    zweites Durchsuchen grosser Ordner kostet spuerbar Zeit.
    geplant_fn(anzahl): erfaehrt vorab, wie viele Dateien wirklich gelesen
    werden - fuer eine ehrliche Fortschrittsanzeige (siehe alles_indexieren).
    """
    soll_abbrechen = soll_abbrechen or (lambda: False)
    ordner = os.path.abspath(os.path.expanduser(ordner))
    alle_eintraege = lade_bestehenden_index()

    eintraege_dieser_ordner = [e for e in alle_eintraege if e["datei"].startswith(ordner + os.sep)]
    andere_eintraege = [e for e in alle_eintraege if not e["datei"].startswith(ordner + os.sep)]

    bekannt = {e["datei"]: e.get("geaendert", 0) for e in eintraege_dieser_ordner}
    # Mit welchem Stand der Leseroutine eine Datei eingelesen wurde (siehe
    # LESER_STAND in dateien.py). Eintraege von vor dieser Angabe gelten
    # als Stand 1.
    gelesen_mit = {e["datei"]: e.get("leser", 1) for e in eintraege_dieser_ordner}
    aktuelle_dateien = set(dateien if dateien is not None else dateien_im_ordner(ordner))
    # Als Menge, nicht als Liste: unten wird fuer JEDEN bekannten Eintrag
    # nachgesehen, ob seine Datei dazugehoert. Mit einer Liste waechst das
    # quadratisch - bei 20.000 Abschnitten und 2.000 geaenderten Dateien
    # sind das 40 Millionen Vergleiche, bevor ueberhaupt gelesen wird.
    zu_verarbeiten = {p for p in aktuelle_dateien
                      if _muss_gelesen_werden(p, bekannt, gelesen_mit)}
    if geplant_fn:
        geplant_fn(len(zu_verarbeiten))

    # Die bisherigen Eintraege der Dateien, die gleich neu gelesen werden.
    # Sie bleiben bis zum Ende des Laufs im Index stehen (siehe
    # _zwischenstand) - sonst waere eine geaenderte Datei waehrend des
    # Laufs gar nicht auffindbar, und nach einem Abbruch bliebe sie es.
    alte_eintraege = {}
    for e in eintraege_dieser_ordner:
        if e["datei"] in zu_verarbeiten:
            alte_eintraege.setdefault(e["datei"], []).append(e)

    eintraege_dieser_ordner = [
        e for e in eintraege_dieser_ordner
        if e["datei"] in aktuelle_dateien and e["datei"] not in zu_verarbeiten
    ]

    if not zu_verarbeiten:
        ergebnis = andere_eintraege + eintraege_dieser_ordner
        speichere_index(ergebnis)
        return ergebnis

    if modell is None:
        modell = geladenes_modell()

    neue_eintraege = []

    def _datei_verarbeiten(pfad):
        if soll_abbrechen():
            return pfad, None, None
        geaendert = _geaendert_am(pfad)
        text = lies_datei(pfad) if geaendert is not None else None
        return pfad, geaendert, text

    abgebrochen = False
    fertig_zaehler = 0
    # Sortiert, damit ein Lauf reproduzierbar dieselbe Reihenfolge nimmt.
    with ThreadPoolExecutor(max_workers=LESE_THREADS) as pool:
        for pfad, geaendert, text in pool.map(_datei_verarbeiten, sorted(zu_verarbeiten)):
            if soll_abbrechen():
                # Die restlichen Auftraege im Pool kehren sofort zurueck
                # (siehe _datei_verarbeiten), das Warten darauf kostet nichts.
                abgebrochen = True
                continue
            if geaendert is None:
                # Inzwischen geloescht oder verschoben - nichts aufzunehmen,
                # und die alten Eintraege gelten auch nicht mehr.
                alte_eintraege.pop(pfad, None)
                continue
            fertig_zaehler += 1
            if fortschritt_fn:
                fortschritt_fn(fertig_zaehler, os.path.basename(pfad))

            if not text or not text.strip():
                # Datei konnte nicht gelesen werden oder ist leer (z.B.
                # kaputtes PDF, gescanntes Dokument ohne erkennbaren Text).
                # Trotzdem als "verarbeitet" markieren (mit geaendert-
                # Zeitstempel, aber ohne Vektor), damit sie beim nächsten
                # Lauf nicht erneut - erfolglos - verarbeitet wird. In der
                # Suche taucht sie wegen des fehlenden Vektors nicht auf
                # (siehe suche_intern-Filter). Über fehlgeschlagene_dateien()
                # kann man diese Liste einsehen, über
                # entferne_fehlgeschlagene_markierung() einen Neuversuch
                # erzwingen (z.B. nach nachträglicher OCR-Installation).
                neue_eintraege.append({
                    "datei": pfad,
                    "text": "",
                    "text_fuer_analyse": None,
                    "geaendert": geaendert,
                    "ohne_inhalt": True,
                    "leser": leser_stand(pfad),
                })
                continue

            dateiname_ohne_endung = os.path.splitext(os.path.basename(pfad))[0]

            for abschnitt in in_abschnitte_teilen(text):
                text_fuer_analyse = f"Dokument: {dateiname_ohne_endung}\nInhalt: {abschnitt}"
                neue_eintraege.append({
                    "datei": pfad,
                    "text": abschnitt,
                    "text_fuer_analyse": text_fuer_analyse,
                    "geaendert": geaendert,
                    "leser": leser_stand(pfad),
                })

    # KI-Vektoren in kleinen Batches berechnen statt alles auf einmal.
    # Vorher wurde modell.encode() einmal für ALLE gesammelten Textabschnitte
    # aufgerufen - bei vielen Dateien konnte das (besonders im CPU-Modus,
    # siehe lade_modell()) mehrere Minuten dauern, OHNE dass die GUI
    # währenddessen einen Fortschritt anzeigen konnte. Es sah dann so aus,
    # als sei die App eingefroren. Jetzt wird in Batches gerechnet und nach
    # jedem Batch fortschritt_fn(None, ...) aufgerufen, damit die GUI eine
    # eigene, laufende Statusmeldung für diese Phase zeigen kann.
    # Zwischenspeicherung alle SPEICHER_INTERVALL Batches - ermöglicht
    # "Suchen während der Indexierung": statt bis zum kompletten Abschluss
    # (kann bei vielen Dateien über eine Stunde dauern) zu warten, kann man
    # schon nach den ersten fertig verarbeiteten Batches danach suchen,
    # während der Rest im Hintergrund weiterläuft.
    SPEICHER_INTERVALL = 3
    BATCH_GROESSE = 16
    zu_kodierende = [e for e in neue_eintraege if e.get("text_fuer_analyse")]
    if zu_kodierende and not abgebrochen:
        gesamt_batches = math.ceil(len(zu_kodierende) / BATCH_GROESSE)
        for batch_start in range(0, len(zu_kodierende), BATCH_GROESSE):
            if soll_abbrechen():
                abgebrochen = True
                break
            batch = zu_kodierende[batch_start:batch_start + BATCH_GROESSE]
            texte = [e["text_fuer_analyse"] for e in batch]
            vektoren = modell.encode(texte, show_progress_bar=False, normalize_embeddings=True)
            for e, v in zip(batch, vektoren, strict=True):
                e["vektor"] = v
                del e["text_fuer_analyse"]

            aktueller_batch = batch_start // BATCH_GROESSE + 1
            if fortschritt_fn:
                # idx=None signalisiert: das ist die Berechnungs-Phase, nicht
                # ein neu gelesenes Dokument. Uebergeben werden die Zahlen,
                # nicht ein fertiger Satz - frueher stand hier ein deutscher
                # Text, den die Oberflaeche per Suchmuster wieder zerlegte,
                # und in der englischen Oberflaeche erschien er auf Deutsch.
                fortschritt_fn(None, (aktueller_batch, gesamt_batches))

            ist_letzter_batch = aktueller_batch == gesamt_batches
            if aktueller_batch % SPEICHER_INTERVALL == 0 or ist_letzter_batch:
                speichere_index(andere_eintraege + eintraege_dieser_ordner
                                + _zwischenstand(neue_eintraege, alte_eintraege))

    # Bei einem Abbruch bleiben halb fertige Dateien mit ihrem alten Stand
    # stehen (siehe _zwischenstand); ohne Abbruch ist hier alles fertig.
    gesamt = andere_eintraege + eintraege_dieser_ordner + _zwischenstand(neue_eintraege, alte_eintraege)
    for e in gesamt:
        e.pop("text_fuer_analyse", None)
    speichere_index(gesamt)

    return gesamt


def alles_indexieren(ordner_liste, soll_abbrechen, melden):
    """Der komplette Indexlauf ueber alle ueberwachten Ordner.

    soll_abbrechen()  -> True, sobald der Nutzer abbrechen will. Wird
                         zwischen zwei Dateien abgefragt.
    melden(ereignis)  -> bekommt den Fortschritt als Woerterbuch:

        {"art": "datei", "anteil": 0..1, "n": 3, "gesamt": 120, "name": "...",
         "restzeit_sek": 95.0}
        {"art": "vektoren", "batch": 4, "batches": 9, "restzeit_sek": 30.0}

    Rueckgabe: True, wenn der Lauf vollstaendig war, False bei Abbruch.

    Wirft modell.ProgrammUnvollstaendig, wenn das mitgelieferte Modell
    fehlt - die Oberflaeche erklaert diesen Fall eigens.

    Stand vorher in gui.py (_index_bg) und war dort mit dem Zeichnen der
    Statuszeile verwoben. Jetzt rechnet diese Funktion, die Oberflaeche
    zeigt nur an - bei der Umstellung auf eine neue Oberflaeche bleibt sie
    unveraendert.
    """
    # Das Modell wird mit der App ausgeliefert - es gibt keinen Download
    # mehr, der gemeldet werden muesste (siehe kern/modell.py).
    modell = geladenes_modell()

    # Jeden Ordner EINMAL durchsuchen. Die Liste geht an
    # aktualisiere_index() weiter, das vorher jeden Ordner ein zweites Mal
    # durchsucht hat - bei einem grossen Netzlaufwerk eine Minute und mehr.
    ordner_liste = [os.path.abspath(os.path.expanduser(o)) for o in ordner_liste]
    dateien_je_ordner = {o: dateien_im_ordner(o) for o in ordner_liste if os.path.exists(o)}

    # Fortschritt: gezaehlt werden nur die Dateien, die wirklich gelesen
    # werden. Frueher stand hier die Zahl ALLER Dateien - nach einer
    # einzigen geaenderten Datei hiess es dann "Indexiere 1 von 12.000,
    # noch etwa 3 Std", und der Balken blieb fast leer, obwohl der Lauf
    # Sekunden spaeter fertig war. Fuer den Ordner, der gerade dran ist,
    # meldet aktualisiere_index() die echte Zahl (geplant); fuer die noch
    # folgenden steht bis dahin die Zahl ihrer Dateien als Obergrenze.
    zaehler = {"n": 0, "erledigt_vorher": 0, "aktuell": 0}
    noch_offen = {"dateien": sum(len(d) for d in dateien_je_ordner.values())}
    start_zeit = time.time()
    batch_phase_start = {"zeit": None}

    def gesamt():
        return max(zaehler["erledigt_vorher"] + zaehler["aktuell"] + noch_offen["dateien"],
                   zaehler["n"], 1)

    def fortschritt(idx, info):
        if idx is None:
            # KI-Berechnungsphase (Batch X von Y), kein neu gelesenes
            # Dokument. Restzeit anhand des Batch-Fortschritts schaetzen.
            aktueller_batch, gesamt_batches = info
            if batch_phase_start["zeit"] is None:
                batch_phase_start["zeit"] = time.time()
            vergangen = time.time() - batch_phase_start["zeit"]
            rest_sek = None
            if aktueller_batch > 0:
                rest_sek = vergangen / aktueller_batch * (gesamt_batches - aktueller_batch)
            melden({"art": "vektoren", "batch": aktueller_batch,
                    "batches": gesamt_batches, "restzeit_sek": rest_sek})
            return
        zaehler["n"] += 1
        vergangen = time.time() - start_zeit
        summe = gesamt()
        melden({
            "art": "datei",
            "anteil": min(zaehler["n"] / summe, 1.0),
            "n": zaehler["n"],
            "gesamt": summe,
            "name": info,
            "restzeit_sek": vergangen / zaehler["n"] * (summe - zaehler["n"]),
        })

    def geplant(anzahl):
        zaehler["aktuell"] = anzahl

    for o, dateien in dateien_je_ordner.items():
        if soll_abbrechen():
            return False
        noch_offen["dateien"] -= len(dateien)
        batch_phase_start["zeit"] = None
        aktualisiere_index(o, modell=modell, still=True, fortschritt_fn=fortschritt,
                           soll_abbrechen=soll_abbrechen, dateien=dateien, geplant_fn=geplant)
        zaehler["erledigt_vorher"] += zaehler["aktuell"]
        zaehler["aktuell"] = 0

    if soll_abbrechen():
        return False

    # Karteileichen entfernen: Eintraege aus Ordnern, die nicht mehr
    # ueberwacht werden, und Dateien, die es nicht mehr gibt. Ohne das
    # waechst index.pkl endlos und liefert Treffer aus laengst entfernten
    # Ordnern. Laeuft auch, wenn es gar keine Dateien mehr gibt - frueher
    # endete der Lauf in dem Fall vorher, und die alten Eintraege blieben.
    try:
        bereinige_index()
    except Exception as e:
        print(f"[Index] Aufraeumen uebersprungen: {e}")
    return True
