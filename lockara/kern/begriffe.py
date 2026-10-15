#!/usr/bin/env python3
"""
begriffe.py - gleichbedeutende Begriffe fuer die Suche.

WARUM ES DAS GIBT
-----------------
Menschen suchen mit ihren eigenen Worten, Dokumente benutzen die
amtlichen. Wer "GEZ" sucht, findet einen Brief, in dem "Rundfunkbeitrag"
und "Beitragsservice" stehen, aber nie "GEZ". Das Suchmodell kennt solche
Paare nur teilweise: am Testset fand die Suche Dokumente, in denen das
Suchwort NICHT steht, in 9 von 14 Faellen (Arten "bedeutung" und
"umschreibung", Stand 13.10.2026).

GEMESSEN (such_diagnose --testdokumente, 76 Faelle, 13.10.2026)
----------------------------------------------------------------
                        ohne Liste   mit Liste
  alle Faelle             64/76        68/76
  Fehlgriffe                15           12
  bedeutung                4/7          5/7
  umschreibung (Gegenpr.)  5/7          5/7

Gewonnen: GEZ, Anwaltsrechnung, Auto, Spende, Steuererstattung.
Verloren: Handyvertrag (Haushaltsbuch rutscht vor den Vertrag).
Ehrlich gesagt: die Gegenprobe hat sich NICHT verbessert - die Liste
hilft dort, wo sie die Woerter der Anfrage kennt, und die Messung oben
ist dadurch geschoent, dass die Liste nach den Testfaellen entstand.
Geprueft und verworfen: Dokumente mit Begriffstreffer vor dem
Aussortieren durch den Nachsortierer schuetzen - 69/76, aber 19 statt
12 Fehlgriffe.

Diese Liste ergaenzt eine Anfrage um gleichbedeutende Begriffe, bevor
gesucht wird. Aus "GEZ" wird fuer die Suche "GEZ (Rundfunkbeitrag,
Beitragsservice)". Die erste Stufe und der Nachsortierer sehen beides; bei
der Stichwortwertung zaehlt ein Suchwort als gefunden, wenn es selbst ODER
einer seiner Begriffe im Dokument steht.

Die Liste ist nach Lebensbereichen geordnet und bewusst allgemein gehalten
- sie soll beschreiben, wie Menschen in Deutschland ueber ihre Unterlagen
reden, nicht die Testfaelle nachbauen. Gegenprobe: die Faelle der Art
"umschreibung" in tests/suchfaelle.py wurden geschrieben, BEVOR diese Liste
entstand.

PFLEGE
------
Ein Eintrag: Suchwort (klein geschrieben) -> Begriffe, die in Dokumenten
stattdessen stehen. Nur echte Entsprechungen, keine blossen Verwandten:
"Auto" -> "Fahrzeug, Pkw" ja, "Auto" -> "Werkstatt" nein - sonst zeigt die
Suche mehr Falsches. Wirkt in beide Richtungen nur, wenn beide Richtungen
eingetragen sind.

Zweite Regel, gelernt bei der ersten Messung: ein zusammengesetztes Wort
bekommt nur Begriffe derselben Genauigkeit. "Handyvertrag" ->
"Mobilfunkvertrag", aber nicht "Mobilfunk" oder "Tarif"; "Anwaltsrechnung"
-> "Kostenrechnung", aber nicht "Verguetung". Die allgemeinen Woerter
zogen sonst Haushaltsbuch und Verguetungsvereinbarung nach vorn.
"""

import re

from lockara.kern.sprache import wort_trifft

BEGRIFFE = {
    # --- Behoerden, Beitraege, Abkuerzungen des Alltags -------------------
    "gez": ["rundfunkbeitrag", "beitragsservice"],
    "rundfunkgebühr": ["rundfunkbeitrag", "beitragsservice"],
    "rundfunkgebühren": ["rundfunkbeitrag", "beitragsservice"],
    "fernsehgebühren": ["rundfunkbeitrag", "beitragsservice"],
    "finanzamt": ["steuerbescheid", "einkommensteuer"],
    "steuererstattung": ["erstattung", "einkommensteuerbescheid", "steuerbescheid"],
    "steuerrückzahlung": ["erstattung", "steuerbescheid"],
    "steuerbescheid": ["einkommensteuerbescheid"],
    "kfz-steuer": ["kraftfahrzeugsteuer"],
    "jobcenter": ["bürgergeld", "arbeitsagentur"],
    "arbeitsamt": ["agentur für arbeit", "arbeitsagentur"],
    "krankenkasse": ["krankenversicherung"],
    "rente": ["rentenversicherung", "altersrente"],
    "kindergeld": ["familienkasse"],

    # --- Arbeit ----------------------------------------------------------
    "gehaltsabrechnung": ["entgeltabrechnung", "lohnabrechnung", "bezüge"],
    "lohnabrechnung": ["entgeltabrechnung", "gehaltsabrechnung", "bezüge"],
    "lohnzettel": ["entgeltabrechnung", "lohnabrechnung", "gehaltsabrechnung"],
    "gehaltszettel": ["entgeltabrechnung", "gehaltsabrechnung"],
    "gehalt": ["entgelt", "lohn", "bezüge"],
    "lohn": ["entgelt", "gehalt", "bezüge"],
    "kündigung": ["kündigungsschreiben"],
    "rauswurf": ["kündigung"],
    "chef": ["arbeitgeber"],
    "arbeitsvertrag": ["anstellungsvertrag", "dienstvertrag"],
    "zeugnis": ["arbeitszeugnis"],

    # --- Wohnen ----------------------------------------------------------
    "nebenkosten": ["betriebskosten"],
    "nebenkostenabrechnung": ["betriebskostenabrechnung"],
    "betriebskosten": ["nebenkosten"],
    "vermieter": ["vermieterin", "hausverwaltung"],
    "wohnungsmängel": ["mangel", "mietminderung", "schimmel", "feuchtigkeit"],
    "mietmängel": ["mangel", "mietminderung"],
    "mängel": ["mangel"],
    "stromrechnung": ["stromabrechnung", "jahresabrechnung"],
    "heizung": ["heizungsanlage", "therme", "brenner"],
    "handwerker": ["meisterbetrieb"],

    # --- Kommunikation ---------------------------------------------------
    "handyvertrag": ["mobilfunkvertrag"],
    "handy": ["mobilfunk", "mobiltelefon", "smartphone"],
    "handyrechnung": ["mobilfunkrechnung"],
    "telefonrechnung": ["telefonabrechnung", "mobilfunkrechnung", "festnetzrechnung"],
    "internetvertrag": ["dsl-vertrag", "glasfaservertrag", "festnetzvertrag"],
    "wlan": ["internet", "router"],

    # --- Gesundheit ------------------------------------------------------
    "zahnarzt": ["zahnärztin", "zahnärztliche", "zahnmedizin"],
    "zahnarztrechnung": ["privatliquidation", "zahnärztliche"],
    "zahnbehandlung": ["zahnärztliche", "zahnarzt", "zahnmedizin"],
    "arztrechnung": ["privatliquidation", "liquidation"],
    "krankmeldung": ["arbeitsunfähigkeitsbescheinigung", "arbeitsunfähigkeit"],
    "rezept": ["verordnung"],

    # --- Freizeit, Reisen, Vereine ---------------------------------------
    "urlaub": ["reise", "pauschalreise", "reisebestätigung", "flug", "hotel"],
    "ferien": ["urlaub", "reise"],
    "ferienreise": ["reise", "pauschalreise", "urlaub"],
    "reise": ["pauschalreise", "flug", "hotel"],
    "flug": ["flüge", "flugzeiten"],
    "fitnessstudio": ["fitnesscenter", "fitness"],
    "gym": ["fitnessstudio", "fitness"],
    "verein": ["mitgliedschaft", "mitgliedsbeitrag"],
    "vereinsbeitrag": ["mitgliedsbeitrag", "jahresbeitrag"],
    "mitgliedsbeitrag": ["jahresbeitrag"],

    # --- Fahrzeug --------------------------------------------------------
    "auto": ["fahrzeug", "pkw", "kfz"],
    "wagen": ["fahrzeug", "pkw"],
    "autoversicherung": ["kfz-versicherung", "kfz-haftpflicht"],
    "kfz-versicherung": ["kfz-haftpflicht", "fahrzeugversicherung"],
    "tüv": ["hauptuntersuchung"],
    "reifenwechsel": ["radwechsel", "reifen", "räder"],
    "autowerkstatt": ["werkstatt", "werkstattrechnung"],
    "unfall": ["verkehrsunfall", "unfallschaden"],

    # --- Geld, Versicherung, Vertraege -----------------------------------
    "rechnung": ["kostenrechnung", "liquidation"],
    "quittung": ["beleg", "kassenbon"],
    "überweisung": ["zahlung"],
    "mahnung": ["zahlungserinnerung"],
    "spende": ["zuwendungsbestätigung", "spendenquittung", "zuwendung"],
    "spendenquittung": ["zuwendungsbestätigung"],
    "hausratversicherung": ["hausrat"],
    "kreditvertrag": ["darlehensvertrag", "darlehen"],
    "kredit": ["darlehen"],

    # --- Kanzlei: Kosten und Mandat -------------------------------------
    "anwaltsrechnung": ["kostenrechnung", "vergütungsberechnung", "rvg"],
    "anwaltskosten": ["kostenrechnung", "vergütungsberechnung", "rvg"],
    "anwaltshonorar": ["vergütung", "vergütungsvereinbarung", "honorar"],
    "honorarnote": ["kostenrechnung", "honorarrechnung", "vergütungsberechnung"],
    "honorar": ["vergütung", "vergütungsvereinbarung"],
    "vorschuss": ["vorschussanforderung", "kostenvorschuss"],
    "mandant": ["mandantin", "mandantschaft"],
    "vollmacht": ["prozessvollmacht", "bevollmächtigung"],
    "akte": ["aktenzeichen", "az"],

    # --- Kanzlei: Verfahren ---------------------------------------------
    "klage": ["klageschrift", "klageerhebung"],
    "gerichtstermin": ["ladung", "verhandlungstermin"],
    "urteil": ["endurteil", "entscheidung"],
    "berufung": ["berufungsbegründung", "berufungsschrift"],
    "frist": ["fristende", "fristablauf", "vorfrist"],
    "mahnbescheid": ["mahnverfahren"],
    "räumungsklage": ["räumung"],
    "abmahnung": ["abmahnungsschreiben"],
    "abfindung": ["abfindungsbetrag", "aufhebungsvertrag"],
    "kündigungsschutzklage": ["kündigungsschutz", "kschg"],
    "kschg": ["kündigungsschutzgesetz"],
    "scheidung": ["scheidungsantrag", "ehescheidung", "familiengericht"],
    "unterhalt": ["kindesunterhalt", "düsseldorfer tabelle"],
    "erbe": ["erbschaft", "nachlass", "erbschein", "testament"],
    "erbschaft": ["nachlass", "erbschein", "testament"],
    "testament": ["letztwillige verfügung"],
    "nda": ["geheimhaltungsvereinbarung", "non-disclosure", "confidentiality"],
    "geheimhaltungsvereinbarung": ["non-disclosure", "confidentiality", "nda"],
    "datenschutzvertrag": ["auftragsverarbeitung", "avv"],
    "avv": ["auftragsverarbeitung"],
    "gmbh-gründung": ["gesellschaftsvertrag", "satzung", "stammkapital"],
    "bea": ["besonderes elektronisches anwaltspostfach"],
}


def _woerter(anfrage):
    return re.findall(r"[\w\-]+", anfrage.lower())


def ergaenzungen(anfrage):
    """{Suchwort: [Begriffe]} fuer die Woerter der Anfrage, die in der
    Liste stehen. Bindestrich-Woerter ("Kfz-Steuer") zaehlen als ein Wort."""
    gefunden = {}
    for wort in _woerter(anfrage):
        if wort in BEGRIFFE:
            gefunden[wort] = BEGRIFFE[wort]
    return gefunden


def anfrage_fuer_modell(anfrage):
    """Die Anfrage, wie Suchmodell und Nachsortierer sie sehen: ergaenzt
    um die Begriffe in Klammern. Ohne Treffer in der Liste unveraendert."""
    erg = ergaenzungen(anfrage)
    if not erg:
        return anfrage
    zusatz = []
    for begriffe in erg.values():
        for b in begriffe:
            if b not in zusatz and b not in anfrage.lower():
                zusatz.append(b)
    return f"{anfrage} ({', '.join(zusatz)})" if zusatz else anfrage


def wort_oder_begriff_trifft(wort, text):
    """Wie sprache.wort_trifft, zaehlt aber auch die Begriffe des Worts."""
    if wort_trifft(wort, text):
        return True
    return any(wort_trifft(b, text) if " " not in b else b in text
               for b in BEGRIFFE.get(wort, []))
