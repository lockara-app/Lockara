#!/usr/bin/env python3
"""Prueft die Personensuche (kern/personensuche.py) ohne Modell und ohne
Index: Schreibweisen von Namen, Daten, Anschriften, Telefonnummern und die
Einstufung der Treffer. Laeuft in unter einer Sekunde.

    python -m tests.test_personensuche
"""
import sys

from lockara.kern import personensuche as ps


def merkmale(text, **angaben):
    person = ps.Person(**angaben)
    return {s.merkmal for s in ps.abschnitt_pruefen(text, ps.suchplan(person))}


def main():
    fehler = []

    def erwarte(beschreibung, ist, soll):
        if ist != soll:
            fehler.append(f"{beschreibung}: {ist!r} statt {soll!r}")

    sw = dict(name="Sabine Wortmann")

    # --- Namen ---
    erwarte("voller Name", merkmale("Frau Sabine Wortmann, Am Brodhagen 12", **sw), {ps.NAME_VOLL})
    erwarte("Nachname, Vorname", merkmale("Mandantin: Wortmann, Sabine", **sw), {ps.NAME_VOLL})
    erwarte("Grossbuchstaben", merkmale("SABINE WORTMANN", **sw), {ps.NAME_VOLL})
    erwarte("Zeilenumbruch im Namen", merkmale("Sabine\n  Wortmann", **sw), {ps.NAME_VOLL})
    erwarte("Zweiter Vorname", merkmale("Sabine Maria Wortmann", **sw), {ps.NAME_VOLL})
    erwarte("Initial", merkmale("gez. S. Wortmann", **sw), {ps.NAME_TEIL})
    erwarte("Anrede + Nachname", merkmale("Sehr geehrte Frau Wortmann,", **sw), {ps.NAME_TEIL})
    erwarte("Name nicht enthalten", merkmale("Wortmannsdorf liegt in Bayern", **sw), set())
    erwarte("Eingabe umgedreht", merkmale("Sabine Wortmann", name="Wortmann, Sabine"), {ps.NAME_VOLL})
    erwarte("Titel in der Eingabe", merkmale("Sabine Wortmann", name="Dr. Sabine Wortmann"), {ps.NAME_VOLL})

    oz = dict(name="Murat Özdemir")
    erwarte("Umlaut im Dokument", merkmale("Herr Murat Özdemir", **oz), {ps.NAME_VOLL})
    erwarte("Umlaut ausgeschrieben", merkmale("Herr Murat Oezdemir", **oz), {ps.NAME_VOLL})
    erwarte("Eingabe ausgeschrieben", merkmale("Herr Murat Özdemir", name="Murat Oezdemir"), {ps.NAME_VOLL})

    wolf = dict(name="Anna Wolf")
    erwarte("Nachname als Wort im Satz", merkmale("Der Hund bellte wie ein wolf.", **wolf), set())
    erwarte("Nachname gross", merkmale("Rueckruf von Herrn Wolf erbeten", **wolf), {ps.NAME_TEIL})

    erwarte("Doppelname mit Leerraum", merkmale("Petra Müller - Lüdenscheidt", name="Petra Müller-Lüdenscheidt"), {ps.NAME_VOLL})
    erwarte("Namenszusatz", merkmale("Ursula von der Leyen", name="Ursula von der Leyen"), {ps.NAME_VOLL})

    my = dict(name="Mehmet Yılmaz")
    erwarte("tuerkisches i, Dokument ASCII", merkmale("Herrn Mehmet Yilmaz", **my), {ps.NAME_VOLL})
    erwarte("tuerkisches i, Eingabe ASCII", merkmale("Herrn Mehmet Yılmaz", name="Mehmet Yilmaz"), {ps.NAME_VOLL})
    erwarte("Kontoauszug ohne Komma", merkmale("LOHN 09/24 YILMAZ MEHMET", **my), {ps.NAME_VOLL})
    hp = dict(name="Hans-Peter von der Heide")
    erwarte("Initialen mit Bindestrich, Zusatz abgekuerzt", merkmale("Vermieter: H.-P. v. d. Heide", **hp), {ps.NAME_TEIL})
    erwarte("Doppelvorname ohne Bindestrich", merkmale("Ich, Hans Peter von der Heide", **hp), {ps.NAME_VOLL})
    erwarte("Rufname erster Teil", merkmale("Hans von der Heide", **hp), {ps.NAME_VOLL})
    erwarte("Zusatz klein am Zellanfang", merkmale("Mandant: von der Heide · Az", **hp), {ps.NAME_TEIL})
    erwarte("Nur das Wort Heide", merkmale("Wanderung durch die Lüneburger Heide", **hp), set())

    # Die Fundstelle zeigt das Original, nicht die Vergleichsform
    stellen = ps.abschnitt_pruefen("Herr Murat Oezdemir und Frau Elif Özdemir", ps.suchplan(ps.Person(name="Elif Özdemir")))
    erwarte("Fundstelle im Original", [s.treffer for s in stellen if s.merkmal == ps.NAME_VOLL], ["Elif Özdemir"])

    # --- Geburtsdatum ---
    gd = dict(name="Sabine Wortmann", geburtsdatum="02.07.1980")
    for text in ("geb. 02.07.1980", "geb. 2.7.80", "geboren am 2. Juli 1980", "1980-07-02", "geb. 2.7.1980"):
        erwarte(f"Datum {text!r}", ps.GEBURTSDATUM in merkmale(text, **gd), True)
    erwarte("anderes Datum", ps.GEBURTSDATUM in merkmale("12.07.1980", **gd), False)
    erwarte("Datum in Nummer", ps.GEBURTSDATUM in merkmale("Az. 102.07.19801", **gd), False)
    erwarte("Datumseingabe kurz", ps.datum_lesen("2.7.80").isoformat(), "1980-07-02")
    try:
        ps.datum_lesen("31.02.1980")
        fehler.append("31.02. wurde als Datum angenommen")
    except ps.EingabeFehler:
        pass

    # --- Anschrift ---
    for eingabe, text in (("Wittekindstraße 30", "Wittekindstr. 30, 33615 Bielefeld"),
                          ("Wittekindstr. 30", "Wittekindstrasse 30"),
                          ("Am Brodhagen 12, 33613 Bielefeld", "wohnhaft Am  Brodhagen 12"),
                          ("Lange Straße 5a", "Lange Str. 5 a")):
        erwarte(f"Anschrift {eingabe!r} in {text!r}",
                ps.ANSCHRIFT in merkmale(text, name="X Y", anschrift=eingabe), True)
    erwarte("andere Hausnummer", ps.ANSCHRIFT in merkmale("Wittekindstraße 3", name="X Y", anschrift="Wittekindstraße 30"), False)

    # --- E-Mail, Telefon, weitere ---
    erwarte("E-Mail", ps.EMAIL in merkmale("Mail: S.Wortmann@Example.de.", name="X Y", email="s.wortmann@example.de"), True)
    for text in ("Tel. 0521 / 12 34 56", "+49 521 123456", "(0521) 123456", "+49 (0)521 123456"):
        erwarte(f"Telefon {text!r}", ps.TELEFON in merkmale(text, name="X Y", telefon="0521 123456"), True)
    erwarte("andere Nummer", ps.TELEFON in merkmale("Tel. 0521 123457", name="X Y", telefon="0521 123456"), False)
    erwarte("Aktenzeichen", ps.WEITERE in merkmale("ArbG Bielefeld 2 Ca 311 / 24", name="X Y", weitere=["2 Ca 311/24"]), True)
    erwarte("Steuer-ID gegliedert", ps.WEITERE in merkmale("IdNr. 12 345 678 901", name="X Y", weitere=["12345678901"]), True)
    erwarte("IBAN gegliedert", ps.WEITERE in merkmale("DE89 3704 0044 0532 0130 00", name="X Y", weitere=["DE89370400440532013000"]), True)
    erwarte("Aktenzeichen laenger", ps.WEITERE in merkmale("2 Ca 3115/24", name="X Y", weitere=["2 Ca 311/24"]), False)

    # --- IBAN ---
    erwarte("gueltige IBAN", len(ps.ibans_in("IBAN: DE89 3704 0044 0532 0130 00")), 1)
    erwarte("falsche Pruefziffer", len(ps.ibans_in("IBAN: DE88 3704 0044 0532 0130 00")), 0)

    # --- Stufen ---
    erwarte("Stufe voll + Datum", ps.stufe_fuer({ps.NAME_VOLL, ps.GEBURTSDATUM}), ps.SICHER)
    erwarte("Stufe Nachname + Anschrift", ps.stufe_fuer({ps.NAME_TEIL, ps.ANSCHRIFT}), ps.SICHER)
    erwarte("Stufe voll", ps.stufe_fuer({ps.NAME_VOLL, ps.NAME_TEIL}), ps.WAHRSCHEINLICH)
    erwarte("Stufe nur E-Mail", ps.stufe_fuer({ps.EMAIL}), ps.WAHRSCHEINLICH)
    erwarte("Stufe Nachname + Datum", ps.stufe_fuer({ps.NAME_TEIL, ps.GEBURTSDATUM}), ps.WAHRSCHEINLICH)
    erwarte("Stufe nur Nachname", ps.stufe_fuer({ps.NAME_TEIL}), ps.PRUEFEN)
    erwarte("Stufe nur IBAN", ps.stufe_fuer({ps.IBAN}), None)

    # --- Eingabefehler ---
    try:
        ps.suchplan(ps.Person(name="  "))
        fehler.append("leerer Name wurde angenommen")
    except ps.EingabeFehler:
        pass

    for f in fehler:
        print("FEHLER:", f)
    print(f"Personensuche: {len(fehler)} Fehler")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
