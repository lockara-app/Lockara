"""
personen.py - 50 Dokumente fuer die Personensuche (DSGVO).

Ein erfundenes Buero in Bielefeld: Kanzlei Hellweg & Sommer mit eigener
Personalabteilung und Buchhaltung. Fuenf Testpersonen kommen in vielen
Dokumenten vor - in allen Formen, die echte Akten hergeben. Alle Namen,
Anschriften, Nummern und Konten sind erfunden; Strassen und Gerichte sind
echt, damit es aussieht wie eine echte Ablage.

    KS  Katharina Schaefer-Uhlmann   Mandantin, Doppelname, Baurecht
    MY  Mehmet Yilmaz (mit tuerkischem i) Mitarbeiter; dazu ein NAMENSVETTER
                                     mit anderem Geburtsdatum und seine Frau
    HP  Hans-Peter von der Heide     Vermieter, Namenszusatz, Schaltjahr-Geburtstag
    SW  Sophie Wagner                Bewerberin, Allerweltsname
    JW  Juergen Weiss (mit sz)       Steuermandant; "weiss" ist auch ein Wort

FALLEN, die die Suche bestehen muss:
  - Doppelname am Zeilenende umbrochen ("Schäfer-" / "Uhlmann")
  - "Yılmaz" / "Yilmaz" / "YILMAZ MEHMET" wie auf Kontoauszuegen
  - "H.-P. v. d. Heide", "Hans Peter" ohne Bindestrich, "29.2.1956"
  - Geburtsdatum als Excel-Datumszelle, als "3. Januar 1990", als "03.01.90"
  - Steuer-ID und IBAN mit und ohne Leerzeichen
  - Telefonnummern in fuenf Schreibweisen
  - Namensvetter Mehmet Yilmaz *11.05.1972 (darf hoechstens "wahrscheinlich" sein)
  - "Richard Wagner", "Thomas Wagner", "Lüneburger Heide", "Frau Uhlmann",
    "Weiß jemand ...", "Schwarz-Weiß-Druck"
  - etwa zehn Dokumente ohne jeden Bezug

SOLL beschreibt fuer jedes Dokument, was die Personensuche finden muss:
    SOLL[datei] = {"KS": "sicher", "SW": "pruefen", ...}
Fehlt eine Person, darf sie in dieser Datei NICHT gefunden werden.
NICHT_GEMEINT enthaelt Treffer, die richtig erkannt werden, aber eine
andere Person meinen (Namensvetter, Richard Wagner) - die Suche kann das
nicht wissen, darf sie aber nicht als "sicher" einstufen.

Erzeugen:  venv/bin/python -m werkzeuge.testdokumente.personen
Messen:    venv/bin/python -m werkzeuge.personensuche_messen
"""

import os
import sys

from lockara.kern.pfade import PROJEKT_ORDNER

from .bausteine import Dok, schreiben

ZIEL = os.path.join(PROJEKT_ORDNER, "tests", "personendokumente")


def iban(blz, konto):
    """Eine deutsche IBAN mit richtiger Pruefziffer (erfundene Konten)."""
    bban = f"{blz:08d}{konto:010d}"
    zahl = int(bban + "131400")          # D=13, E=14, Pruefziffer 00
    pruef = 98 - zahl % 97
    roh = f"DE{pruef:02d}{bban}"
    return " ".join(roh[i:i + 4] for i in range(0, len(roh), 4))


IBAN_KS = iban(48050161, 4471120)
IBAN_MY = iban(48050161, 9902231)
IBAN_KANZLEI = iban(48050161, 1000815)

# Die Eingaben, mit denen gemessen wird - so wuerde eine Mitarbeiterin sie
# in das Formular tippen.
PERSONEN = {
    "KS": dict(name="Katharina Schäfer-Uhlmann", geburtsdatum="17.09.1984",
               anschrift="Detmolder Straße 112, 33604 Bielefeld",
               email="k.schaefer-uhlmann@beispiel.de", telefon="0521 9876543",
               weitere=["12 O 245/24", "M-20419", IBAN_KS.replace(" ", "")]),
    "MY": dict(name="Mehmet Yılmaz", geburtsdatum="03.01.1990",
               anschrift="Heeper Straße 77a", email="mehmet.yilmaz90@beispiel.de",
               telefon="0176 55512345", weitere=["P-0815", IBAN_MY]),
    "HP": dict(name="Hans-Peter von der Heide", geburtsdatum="29.02.1956",
               anschrift="Am Sparrenberg 3b, 33602 Bielefeld", telefon="0521 445566",
               weitere=["7 C 1043/24"]),
    "SW": dict(name="Sophie Wagner", geburtsdatum="22.06.1999",
               anschrift="Niedermühlenkamp 9", email="sophie.wagner@beispiel.de",
               telefon="+49 151 23456789"),
    "JW": dict(name="Jürgen Weiß", geburtsdatum="08.07.1961", anschrift="Kesselbrink 4",
               weitere=["K-3301", "12345678901"]),
}

KOPF = ["Hellweg & Sommer Rechtsanwälte",
        "Niederwall 23 · 33602 Bielefeld · Tel. 0521 000111 · kanzlei@hellweg-sommer.example"]
FUELL = ("Wir nehmen Bezug auf die bisherige Korrespondenz und bitten um Beachtung der "
         "nachfolgenden Hinweise. Sollten Sie Fragen haben, stehen wir Ihnen zu den üblichen "
         "Bürozeiten gern zur Verfügung.")

M = "Mandanten/"
MKS = M + "Schäfer-Uhlmann 245-24/"
MHP = M + "von der Heide 1043-24/"
P = "Personal/"
B = "Buchhaltung/"
S = "Steuer Weiß/"
K = "Korrespondenz/"
V = "Verwaltung/"

DOKUMENTE = []
SOLL = {}
NICHT_GEMEINT = set()     # (datei, person)


def dok(datei, art, titel, inhalt, soll=None, stempel=None, nicht_gemeint=()):
    DOKUMENTE.append(Dok(datei, art, titel, inhalt, stempel=stempel))
    SOLL[datei] = dict(soll or {})
    for p in nicht_gemeint:
        NICHT_GEMEINT.add((datei, p))


# ===========================================================================
# KS - Katharina Schäfer-Uhlmann (Mandantin, Baumängel)
# ===========================================================================

dok(MKS + "Klageschrift_LG.docx", "docx", "Klage", KOPF + [
    "", "An das Landgericht Bielefeld", "Niederwall 71, 33602 Bielefeld", "",
    "# Klage",
    "der Frau Katharina Schäfer-Uhlmann, Detmolder Straße 112, 33604 Bielefeld – Klägerin –",
    "Prozessbevollmächtigte: Rechtsanwälte Hellweg & Sommer",
    "gegen",
    "die Bauwerk Ostwestfalen GmbH, vertreten durch den Geschäftsführer Uwe Krämer, "
    "Eckendorfer Straße 40, 33609 Bielefeld – Beklagte –",
    "wegen Mängelbeseitigung aus Bauvertrag. Vorläufiger Streitwert: 48.200,00 EUR", "",
    "## Anträge",
    "Die Beklagte wird verurteilt, an die Klägerin 48.200,00 EUR nebst Zinsen zu zahlen.",
    "## Begründung",
    "Die Klägerin beauftragte die Beklagte mit Vertrag vom 14.02.2023 mit der Errichtung "
    "eines Einfamilienhauses. Bereits bei der Abnahme zeigten sich Feuchtigkeitsschäden im "
    "Kellergeschoss. " + FUELL,
    "---",
    "Beweis: Gutachten des Sachverständigen Dipl.-Ing. Frank Obermeier vom 30.06.2024.",
    "Die Mängel wurden mit Schreiben vom 02.04.2024 gerügt; eine Frist zur Nacherfüllung ist "
    "fruchtlos verstrichen. " + FUELL,
    "", "Dr. Clara Sommer", "Rechtsanwältin",
], soll={"KS": "sicher"})

dok(MKS + "Scan_20240903_0007.pdf", "scan", "Ladung", [
    "Landgericht Bielefeld", "Niederwall 71 · 33602 Bielefeld", "",
    "Geschäftszeichen: 12 O 245/24", "",
    "Rechtsanwälte Hellweg & Sommer", "Niederwall 23", "33602 Bielefeld", "",
    "# Ladung zum frühen ersten Termin",
    "In dem Rechtsstreit",
    "Schäfer-Uhlmann ./. Bauwerk Ostwestfalen GmbH",
    "wird Termin zur mündlichen Verhandlung bestimmt auf",
    "Mittwoch, den 16.10.2024, 10:15 Uhr, Saal 2.104.",
    "Das persönliche Erscheinen der Parteien wird angeordnet.",
    "", "Auf Anordnung", "Brandt, Justizbeschäftigte",
], stempel="EINGANG 03. SEP. 2024", soll={"KS": "sicher"})

dok(MKS + "Vollmacht_unterschrieben.pdf", "scan", "Vollmacht", [
    "# VOLLMACHT", "",
    "Hiermit wird den Rechtsanwälten Hellweg & Sommer, Bielefeld,",
    "in Sachen KATHARINA SCHÄFER-UHLMANN",
    "geb. am 17.09.1984",
    "wegen Ansprüchen aus dem Bauvertrag mit der Bauwerk Ostwestfalen GmbH",
    "Vollmacht erteilt zur Prozessführung, zur Begründung und Aufhebung von",
    "Vertragsverhältnissen sowie zur Abgabe und Entgegennahme von Willenserklärungen.",
    "", "Bielefeld, 08.07.2024", "", "______________________", "(Unterschrift)",
], soll={"KS": "sicher"})

dok(MKS + "Mail_Mandantin_2024-08-12.txt", "txt", "E-Mail", [
    "Von: k.schaefer-uhlmann@beispiel.de",
    "An: kanzlei@hellweg-sommer.example",
    "Datum: 12.08.2024 21:47",
    "Betreff: Fotos Keller",
    "",
    "Sehr geehrte Frau Dr. Sommer,",
    "anbei die Fotos vom Keller nach dem Starkregen letzte Woche. Das Wasser stand wieder "
    "etwa fünf Zentimeter hoch. Ich hoffe, das hilft für das Verfahren.",
    "",
    "Viele Grüße",
    "Katharina",
], soll={"KS": "wahrscheinlich"})

dok(MKS + "Aktennotiz_Telefonat.md", "md", "Aktennotiz", [
    "# Aktennotiz 245/24", "",
    "**05.09.2024, 11:20 Uhr** – Fr. Schaefer-Uhlmann rief an, bittet um Rückruf wegen des "
    "Termins am 16.10. Erreichbar ab 17 Uhr unter 0521/98 765 43.",
    "",
    "- Termin besprochen, persönliches Erscheinen erklärt",
    "- Sachverständiger soll geladen werden",
    "",
    "_CS_",
], soll={"KS": "sicher"})

dok(MKS + "Kostenvorschuss_Rechnung.pdf", "pdf", "Vorschussrechnung", KOPF + [
    "",
    "Frau",
    "Katharina Schäfer-Uhlmann",
    "Detmolder Str. 112",
    "33604 Bielefeld",
    "",
    "# Vorschussrechnung Nr. 2024-0712",
    "Mandantennummer: M-20419 · Akte 245/24",
    "Vorschuss gemäß § 9 RVG für das Verfahren vor dem Landgericht Bielefeld",
    "1,3 Verfahrensgebühr Nr. 3100 VV RVG: 1.732,90 EUR",
    "Auslagenpauschale Nr. 7002 VV RVG: 20,00 EUR",
    "19 % Umsatzsteuer: 333,05 EUR",
    "Gesamtbetrag: 2.085,95 EUR",
    "",
    f"Bitte überweisen Sie auf unser Konto: {IBAN_KANZLEI}",
], soll={"KS": "sicher"})

dok(MKS + "Gutachten_Bausachverstaendiger.pdf", "pdf", "Gutachten", [
    "# Gutachten zur Feuchtigkeit im Kellergeschoss",
    "Dipl.-Ing. Frank Obermeier · öffentlich bestellter und vereidigter Sachverständiger",
    "Gutachten-Nr. 2024-118 vom 30.06.2024", "",
    "## 1. Auftrag",
    "Auftraggeberin: K. Schäfer-Uhlmann",
    "Gegenstand: Einfamilienhaus, Baujahr 2023",
    "## 2. Ortstermin",
    "Der Ortstermin fand am 21.06.2024 statt. Anwesend waren die Auftraggeberin sowie ein "
    "Vertreter der ausführenden Firma. " + FUELL,
    "---",
    "## 3. Befund",
    "An der Nordwand wurden Feuchtigkeitswerte von bis zu 6,8 Masseprozent gemessen. Die "
    "Abdichtung nach DIN 18533 ist nicht fachgerecht ausgeführt. " + FUELL,
    "---",
    "## 4. Objektanschrift",
    "Detmolder Str. 112, 33604 Bielefeld (Flur 7, Flurstück 412)",
    "## 5. Ergebnis",
    "Die Kosten der Mängelbeseitigung werden auf 46.500 EUR netto geschätzt.",
], soll={"KS": "sicher"})

dok(B + "Kontoauszug_Sept_2024.pdf", "scan", "Kontoauszug", [
    "Sparkasse Bielefeld · Kontoauszug 9/2024 · Blatt 1",
    f"Konto {IBAN_KANZLEI} · Hellweg & Sommer Rechtsanwälte", "",
    "Buchung   Wert    Vorgang                                Betrag",
    "02.09.    02.09.  GUTSCHRIFT SCHAEFER-UHLMANN K           2.085,95",
    f"                  {IBAN_KS.replace(' ', '')}",
    "                  VORSCHUSS 245/24",
    "05.09.    05.09.  LASTSCHRIFT STADTWERKE BIELEFELD          -312,40",
    "27.09.    27.09.  LOHN/GEHALT 09/24 YILMAZ MEHMET          -3.104,22",
    f"                  {IBAN_MY.replace(' ', '')}",
    "30.09.    30.09.  ENTGELT KONTOFUEHRUNG                       -14,90",
], soll={"KS": "sicher", "MY": "sicher"})

dok(MKS + "Fallbesprechung_Folien.pptx", "pptx", "Fallbesprechung", [
    ("Fallbesprechung 245/24", ["Mandantin K. Schäfer-Uhlmann", "Baumängel Keller"]),
    ("Stand", ["Klage eingereicht am 19.07.2024", "Az. 12 O 245/24", "Termin 16.10.2024"]),
    ("Risiken", ["Abnahme ohne Vorbehalt?", "Verjährung unproblematisch"]),
], soll={"KS": "sicher"})

# ===========================================================================
# MY - Mehmet Yılmaz (Mitarbeiter) und Namensvetter
# ===========================================================================

dok(P + "Gehaltsabrechnung_2024-09_P0815.docx", "docx", "Gehaltsabrechnung", [
    "Hellweg & Sommer Rechtsanwälte · Personalabteilung", "",
    "Herrn",
    "Mehmet Yılmaz",
    "Heeper Str. 77 a",
    "33607 Bielefeld", "",
    "# Entgeltabrechnung September 2024",
    "Personalnummer: P-0815 · Steuerklasse III · Konfession: –",
    "Bruttogehalt: 4.150,00 EUR",
    "Lohnsteuer: 412,16 EUR · Solidaritätszuschlag: 0,00 EUR",
    "Sozialversicherung (AN-Anteil): 633,62 EUR",
    "Auszahlungsbetrag: 3.104,22 EUR",
    f"Überweisung auf: {IBAN_MY}",
], soll={"MY": "sicher"})

dok(P + "Arbeitsvertrag_Yilmaz.docx", "docx", "Arbeitsvertrag", [
    "# Arbeitsvertrag", "",
    "zwischen Hellweg & Sommer Rechtsanwälte, Niederwall 23, 33602 Bielefeld – Arbeitgeber –",
    "und",
    "Herrn Mehmet Yilmaz, geb. 03.01.1990, wohnhaft Heeper Straße 77a, 33607 Bielefeld "
    "– Arbeitnehmer –",
    "## § 1 Beginn und Tätigkeit",
    "Das Arbeitsverhältnis beginnt am 01.03.2022. Der Arbeitnehmer wird als "
    "Rechtsanwaltsfachangestellter beschäftigt. " + FUELL,
    "## § 2 Arbeitszeit",
    "Die regelmäßige Arbeitszeit beträgt 39 Stunden pro Woche.",
], soll={"MY": "sicher"})

dok(P + "Mitarbeiterliste_2024.xlsx", "xlsx", "Mitarbeiterliste", {"Mitarbeiter": [
    ["Nachname", "Vorname", "Geburtsdatum", "Personalnummer", "Funktion"],
    ["Sommer", "Clara", __import__("datetime").datetime(1978, 4, 2), "P-0101", "Partnerin"],
    ["Hellweg", "Bernd", __import__("datetime").datetime(1965, 11, 19), "P-0102", "Partner"],
    ["Yılmaz", "Mehmet", __import__("datetime").datetime(1990, 1, 3), "P-0815", "ReFa"],
    ["Wagner", "Thomas", __import__("datetime").datetime(1987, 8, 30), "P-0816", "ReFa"],
    ["Becker", "Sophie", __import__("datetime").datetime(2001, 2, 14), "P-0820", "Auszubildende"],
    ["Krüger", "Anja", __import__("datetime").datetime(1993, 6, 22), "P-0821", "Buchhaltung"],
    ["Novak", "Petra", __import__("datetime").datetime(1970, 12, 1), "P-0822", "Empfang"],
]}, soll={"MY": "sicher", "SW": "pruefen"}, nicht_gemeint=["SW"])

dok(P + "Notfallkontakte.docx", "docx", "Notfallkontakte", [
    "# Notfallkontakte der Mitarbeitenden", "Stand: 01.09.2024 – vertraulich", "",
    "Clara Sommer – Ehemann Jens Sommer, 0171 2223334",
    "Bernd Hellweg – Tochter Lisa Hellweg, 0160 9998887",
    "Mehmet Yılmaz – Ehefrau Ayşe Yılmaz, 0176 55512346; eigene Nummer 0176 55512345",
    "Anja Krüger – Mutter Gisela Krüger, 05221 445566",
], soll={"MY": "sicher"})

dok(P + "Zeugnis_Entwurf_Yilmaz.docx", "docx", "Zeugnis", [
    "# Zwischenzeugnis", "",
    "Herr Mehmet Yılmaz, geboren am 3. Januar 1990, ist seit dem 1. März 2022 in unserer "
    "Kanzlei als Rechtsanwaltsfachangestellter tätig.",
    "Herr Yılmaz erledigt die ihm übertragenen Aufgaben stets zu unserer vollsten "
    "Zufriedenheit. " + FUELL,
], soll={"MY": "sicher"})

dok(P + "Scan_Krankmeldung.pdf", "scan", "AU-Bescheinigung", [
    "# Arbeitsunfähigkeitsbescheinigung",
    "Krankenkasse: AOK NordWest", "",
    "Name, Vorname des Versicherten",
    "YILMAZ, MEHMET          geb. am 03.01.90", "",
    "arbeitsunfähig seit 16.09.2024",
    "voraussichtlich arbeitsunfähig bis einschließlich 20.09.2024",
    "festgestellt am 16.09.2024", "",
    "Praxis Dr. med. Ines Hartwig, Allgemeinmedizin",
], soll={"MY": "sicher"})

dok(P + "Unfallbericht_Betrieb.pdf", "pdf", "Unfallanzeige", [
    "# Interne Unfallmeldung",
    "Datum des Unfalls: 11.06.2024, ca. 15:30 Uhr", "",
    "Verletzte Person: Herr Yilmaz (Personalnr. P-0815)",
    "Hergang: Beim Tragen von Aktenordnern im Treppenhaus umgeknickt.",
    "Erste Hilfe durch: Frau Krüger",
    "Ärztliche Behandlung: ja, Durchgangsarzt",
], soll={"MY": "sicher"})

dok(K + "Hochzeitseinladung.txt", "txt", "Einladung", [
    "Liebe Kolleginnen und Kollegen,",
    "",
    "Ayşe & Mehmet Yılmaz laden euch herzlich zur Feier ihres zehnten Hochzeitstages ein:",
    "Samstag, 23. November 2024, ab 18 Uhr im Ravensberger Park.",
    "",
    "Um Rückmeldung bis Ende Oktober wird gebeten.",
], soll={"MY": "wahrscheinlich"})

dok(K + "Scan_Zeugenaussage.pdf", "scan", "Zeugenaussage", [
    "Polizeipräsidium Bielefeld", "Verkehrsunfallaufnahme", "",
    "# Zeugenvernehmung",
    "Zeuge: Mehmet Yılmaz, geb. 11.05.1972, wohnhaft in Herford, Bünder Straße 15",
    "Zur Sache: Ich stand an der Ampel Jöllenbecker Straße und sah, wie der rote Kombi "
    "bei Rot über die Kreuzung fuhr.",
    "", "Selbst gelesen, genehmigt und unterschrieben.",
], soll={"MY": "wahrscheinlich"}, nicht_gemeint=["MY"])

dok(V + "Dienstplan_Oktober.xlsx", "xlsx", "Dienstplan", {"Oktober": [
    ["Woche", "Empfang", "Telefon", "Postausgang"],
    ["KW 40", "Novak", "Yılmaz", "Wagner T."],
    ["KW 41", "Novak", "Becker", "Yılmaz"],
    ["KW 42", "Krüger", "Wagner T.", "Becker"],
    ["KW 43", "Novak", "Yılmaz", "Krüger"],
]}, soll={"MY": "pruefen", "SW": "pruefen"}, nicht_gemeint=["SW"])

# ===========================================================================
# HP - Hans-Peter von der Heide (Vermieter)
# ===========================================================================

dok(MHP + "Klage_Raeumung_7C1043-24.docx", "docx", "Räumungsklage", KOPF + [
    "", "An das Amtsgericht Bielefeld", "",
    "# Klage auf Räumung und Herausgabe",
    "des Herrn von der Heide, Hans-Peter, geb. 29.02.1956, Am Sparrenberg 3b, 33602 Bielefeld "
    "– Kläger –",
    "gegen",
    "Herrn Dennis Kowalski, Am Sparrenberg 3b, Wohnung 2. OG links – Beklagter –",
    "Aktenzeichen: 7 C 1043/24",
    "## Begründung",
    "Der Beklagte ist mit zwei Monatsmieten in Verzug (§ 543 Abs. 2 Nr. 3 BGB). " + FUELL,
], soll={"HP": "sicher"})

dok(MHP + "Mietvertrag_Scan.pdf", "scan", "Mietvertrag", [
    "# Mietvertrag über Wohnraum", "",
    "Vermieter: H.-P. v. d. Heide, Am Sparrenberg 3 b, 33602 Bielefeld",
    "Mieter: Dennis Kowalski", "",
    "§ 1 Mieträume: Wohnung im 2. OG links, 3 Zimmer, ca. 74 m²",
    "§ 2 Mietzeit: ab 01.05.2019, unbefristet",
    "§ 3 Miete: 690,00 EUR zzgl. 180,00 EUR Betriebskostenvorauszahlung",
], soll={"HP": "sicher"})

dok(MHP + "Testament_Entwurf.docx", "docx", "Testament", [
    "# Mein letzter Wille", "",
    "Ich, Hans Peter von der Heide, geboren am 29.2.1956 in Gütersloh, verfüge hiermit:",
    "Meine Tochter Merle soll das Haus Am Sparrenberg erhalten. " + FUELL,
    "", "Entwurf – nicht unterschrieben",
], soll={"HP": "sicher"})

dok(MHP + "Grundsteuerbescheid_Scan.pdf", "scan", "Grundsteuerbescheid", [
    "Stadt Bielefeld · Amt für Finanzen", "",
    "Herrn", "Hans-Peter von der Heide", "Postfach 10 11 12", "33511 Bielefeld", "",
    "# Grundsteuerbescheid 2025",
    "Kassenzeichen 4711.0815.2025",
    "Die Grundsteuer wird auf 642,30 EUR jährlich festgesetzt.",
], soll={"HP": "wahrscheinlich"})

dok(K + "Rundschreiben_Mieter.docx", "docx", "Rundschreiben", [
    "Hans-Peter von der Heide · Am Sparrenberg 3b · 33602 Bielefeld · Tel. 0521 / 44 55 66", "",
    "An alle Mieterinnen und Mieter", "",
    "# Ankündigung Treppenhausrenovierung",
    "Ab dem 04.11.2024 wird das Treppenhaus gestrichen. " + FUELL,
], soll={"HP": "sicher"})

dok(K + "Reisebericht_Lueneburger_Heide.md", "md", "Reisebericht", [
    "# Betriebsausflug 2024: Lüneburger Heide", "",
    "Mit dem Bus ging es früh los. In der Heide blühte das Heidekraut noch, und im "
    "Heide-Hotel gab es Buchweizentorte. Von der Heide aus fuhren wir weiter nach Celle.",
    "",
    "Fazit: Nächstes Jahr wieder!",
# "Von der Heide aus" am Satzanfang ist von "Herr Von der Heide" nicht zu
# unterscheiden - deshalb nur "pruefen", nie mehr.
], soll={"HP": "pruefen"}, nicht_gemeint=["HP"])

# ===========================================================================
# SW - Sophie Wagner (Bewerberin)
# ===========================================================================

dok(P + "Bewerbung_Wagner_Sophie.pdf", "pdf", "Bewerbung", [
    "# Lebenslauf", "",
    "Sophie Wagner",
    "Niedermühlenkamp 9 · 33604 Bielefeld",
    "Tel. 0151 / 234 567 89 · sophie.wagner@beispiel.de",
    "geboren am 22. Juni 1999 in Lemgo", "",
    "## Ausbildung",
    "2016–2019 Ausbildung zur Rechtsanwaltsfachangestellten, Kanzlei Möller, Detmold",
    "## Berufserfahrung",
    "seit 2019 Rechtsanwaltsfachangestellte, Notariat Dr. Feld, Herford",
], soll={"SW": "sicher"})

dok(P + "Absage_Bewerbung.docx", "docx", "Absage", KOPF + [
    "", "Frau", "Sophie Wagner", "Niedermühlenkamp 9", "33604 Bielefeld", "",
    "## Ihre Bewerbung vom 02.08.2024",
    "Sehr geehrte Frau Wagner,",
    "vielen Dank für Ihr Interesse. Leider müssen wir Ihnen mitteilen, dass wir uns für eine "
    "andere Bewerberin entschieden haben. " + FUELL,
], soll={"SW": "sicher"})

dok(P + "Bewerberliste_Q3.xlsx", "xlsx", "Bewerberliste", {"Q3": [
    ["Name", "E-Mail", "Eingang", "Status"],
    ["Wagner, Sophie", "sophie.wagner@beispiel.de", "02.08.2024", "Absage"],
    ["Brandes, Tim", "tim.brandes@beispiel.de", "05.08.2024", "Gespräch"],
    ["Okafor, Grace", "g.okafor@beispiel.de", "11.08.2024", "Zusage"],
]}, soll={"SW": "sicher"})

dok(P + "Personalgespraech_Notiz.md", "md", "Personalgespräch", [
    "# Personalgespräch Thomas Wagner, 12.09.2024", "",
    "- Herr Wagner wünscht Reduzierung auf 30 Stunden",
    "- Ich weiß nicht, ob das ab Januar klappt – Rücksprache mit Bernd",
    "- Fortbildung Zwangsvollstreckung genehmigt",
], soll={"SW": "pruefen"}, nicht_gemeint=["SW"])

dok(K + "Newsletter_Empfaenger.txt", "txt", "Verteiler", [
    "Verteiler Mandanten-Newsletter (Stand 09/2024)",
    "",
    "a.brandt@beispiel.de",
    "k.schaefer-uhlmann@beispiel.de",
    "info@baeckerei-kaiser.example",
    "sophie.wagner@beispiel.de",
    "t.okafor@beispiel.de",
], soll={"KS": "wahrscheinlich", "SW": "wahrscheinlich"})

dok(K + "Konzertkarten_Betriebsausflug.pdf", "pdf", "Konzertkarten", [
    "# Theater Bielefeld – Sammelbestellung",
    "Richard Wagner: Der fliegende Holländer",
    "Samstag, 30.11.2024, 19:30 Uhr, Großes Haus", "",
    "Teilnehmende: Clara Sommer, Bernd Hellweg, Sophie Becker, Anja Krüger",
    "8 Karten Parkett, Reihe 7",
], soll={"SW": "pruefen"}, nicht_gemeint=["SW"])

dok(K + "Kundenkartei_alt.md", "md", "Kartei", [
    "# Alte Interessentenkartei (vor 2022)", "",
    "| Name | Kontakt | Notiz |",
    "|---|---|---|",
    "| Wagner, S. | sophie.w@beispiel.de | Anfrage Mietrecht 2021 |",
    "| Lorenz, P. | 0521 778899 | erledigt |",
], soll={"SW": "pruefen"})

# ===========================================================================
# JW - Jürgen Weiß (Steuermandant)
# ===========================================================================

dok(S + "Einkommensteuer_2023_Weiss.pdf", "pdf", "Steuererklärung", [
    "# Einkommensteuererklärung 2023 – Anlage Hauptvordruck (Auszug)", "",
    "Steuerpflichtiger: Jürgen Weiß",
    "Anschrift: Kesselbrink 4, 33602 Bielefeld",
    "Identifikationsnummer: 12 345 678 901",
    "Geburtsdatum: 08.07.1961 · Familienstand: verwitwet seit 2019",
    "Einkünfte aus nichtselbständiger Arbeit: 61.420 EUR",
], soll={"JW": "sicher"})

dok(S + "Belegliste_2023.xlsx", "xlsx", "Belegliste", {"Belege 2023": [
    ["Mandant", "Kundennummer", "Beleg", "Betrag"],
    ["Weiss, Juergen", "K-3301", "Handwerkerrechnung Bad", 1840.5],
    ["Weiss, Juergen", "K-3301", "Spende DRK", 150],
    ["Weiss, Juergen", "K-3301", "Fahrtkosten", 2310],
]}, soll={"JW": "sicher"})

dok(S + "Scan_Spendenquittung.pdf", "scan", "Spendenquittung", [
    "Deutsches Rotes Kreuz · Kreisverband Bielefeld", "",
    "# Zuwendungsbestätigung",
    "Name und Anschrift des Zuwendenden:",
    "JÜRGEN WEISS, KESSELBRINK 4, 33602 BIELEFELD",
    "Betrag der Zuwendung: 150,00 EUR – in Worten: einhundertfünfzig",
    "Tag der Zuwendung: 12.12.2023",
], soll={"JW": "sicher"})

dok(V + "Protokoll_Teamsitzung.docx", "docx", "Protokoll", [
    "# Teamsitzung 23.09.2024", "",
    "Weiß jemand, wo die Akte Brinkmann ist? – Wird gesucht.",
    "Herr Weiß von der Steuerberatung hat angerufen, Rückruf durch Bernd.",
    "Druckerpatronen schwarz und farbig bestellen.",
], soll={"JW": "pruefen"})

dok(V + "Farbkonzept_Praesentation.pptx", "pptx", "Farbkonzept", [
    ("Neues Erscheinungsbild", ["Vorschlag der Agentur", "Oktober 2024"]),
    ("Farben", ["Weiß und Anthrazit als Grundfarben", "Akzent: Petrol",
                "Schwarz-Weiß-Druck muss lesbar bleiben"]),
    ("Schrift", ["Serifenlos für Bildschirm", "Serif für Schriftsätze"]),
], soll={"JW": "pruefen"}, nicht_gemeint=["JW"])

# ===========================================================================
# Listen mit mehreren Personen
# ===========================================================================

dok(B + "Offene_Posten_2024.xlsx", "xlsx", "Offene Posten", {"OP": [
    ["Mandant", "Mandantennummer", "Rechnung", "Offen"],
    ["Schäfer-Uhlmann, Katharina", "M-20419", "2024-0712", 0],
    ["von der Heide, Hans-Peter", "M-18877", "2024-0655", 412.3],
    ["Weiss, Juergen", "K-3301", "2024-0590", 238],
    ["Brinkmann, Gisela", "M-17702", "2024-0601", 95],
]}, soll={"KS": "sicher", "HP": "wahrscheinlich", "JW": "sicher"})

dok(V + "Fristenkalender_2024.xlsx", "xlsx", "Fristen", {"Fristen": [
    ["Akte", "Mandant", "Aktenzeichen", "Frist", "Datum"],
    ["245/24", "Schäfer-Uhlmann", "12 O 245/24", "Replik", "30.09.2024"],
    ["245/24", "Schäfer-Uhlmann", "12 O 245/24", "Termin", "16.10.2024"],
    ["1043/24", "von der Heide", "7 C 1043/24", "Klageerwiderung abwarten", "15.10.2024"],
    ["0998/24", "Brinkmann", "2 VI 552/24", "Erbschein", "01.11.2024"],
]}, soll={"KS": "sicher", "HP": "sicher"})

dok(V + "Posteingangsbuch.pdf", "pdf", "Posteingang", [
    "# Posteingangsbuch September 2024", "",
    "02.09. LG Bielefeld – Schäfer-Uhlmann ./. Bauwerk – Ladung",
    "04.09. Finanzamt – Brinkmann – Bescheid",
    "09.09. AG Bielefeld – Kowalski – Klageerwiderung",
    "12.09. Yilmaz, A. – Privatpost, ungeöffnet weitergegeben",
    "18.09. Rechtsanwaltskammer Hamm – Rundschreiben",
], soll={"KS": "pruefen", "MY": "pruefen"}, nicht_gemeint=["MY"])

dok(K + "Rueckrufliste_KW38.txt", "txt", "Rückrufe", [
    "Rückrufe KW 38",
    "",
    "Mo  +49 (0)521 9876543   wg. Termin 16.10.",
    "Di  0151-23456789        Bewerbung, Rückfrage Unterlagen",
    "Mi  05221 / 445566       Fr. Krüger privat",
    "Do  0521 445566          Hausverwaltung Sparrenberg",
], soll={"KS": "wahrscheinlich", "SW": "wahrscheinlich", "HP": "wahrscheinlich"})

# ===========================================================================
# Ohne Bezug zu den Testpersonen
# ===========================================================================

dok(V + "Preisliste_Bueromaterial.xlsx", "xlsx", "Preisliste", {"Preise": [
    ["Artikel", "Einheit", "Preis"],
    ["Kopierpapier A4 weiß", "500 Blatt", 4.99],
    ["Ordner breit", "Stück", 2.49],
    ["Druckerpatrone schwarz", "Stück", 38.9],
]}, soll={})

dok(V + "Hausordnung.pdf", "pdf", "Hausordnung", [
    "# Hausordnung Niederwall 23", "",
    "1. Die Haustür ist ab 20 Uhr verschlossen zu halten.",
    "2. Fahrräder bitte nur im Hof abstellen.",
    "3. Mülltrennung: Papier, Gelber Sack, Restmüll, Bio.",
    "Die Hausverwaltung Ostwestfalen dankt für Ihre Rücksichtnahme.",
], soll={})

dok(V + "IT-Richtlinie.docx", "docx", "IT-Richtlinie", [
    "# IT-Richtlinie der Kanzlei", "",
    "Passwörter sind mindestens 14 Zeichen lang und werden nicht weitergegeben.",
    "Mandantendaten dürfen nur auf den Kanzleiservern gespeichert werden.",
    "USB-Sticks sind nur verschlüsselt erlaubt. " + FUELL,
], soll={})

dok(V + "Speiseplan_KW40.md", "md", "Speiseplan", [
    "# Kantine im Haus – KW 40", "",
    "- Montag: Linsensuppe",
    "- Dienstag: Pickert mit Apfelmus",
    "- Mittwoch: Gemüsecurry",
    "- Donnerstag: Schnitzel Wiener Art",
    "- Freitag: Fisch",
], soll={})

dok(V + "Wartungsvertrag_Kopierer_Scan.pdf", "scan", "Wartungsvertrag", [
    "# Wartungsvertrag Multifunktionssystem", "",
    "Kunde: Hellweg & Sommer Rechtsanwälte",
    "Gerät: Bürosystem MX-4071, Seriennummer 5021334X",
    "Laufzeit: 60 Monate · Seitenpreis s/w 0,6 Cent, Farbe 4,9 Cent",
    "Servicetechniker: Herr Brandt",
], soll={})

dok(V + "Protokoll_Eigentuemerversammlung.docx", "docx", "Eigentümerversammlung", [
    "# Protokoll der Eigentümerversammlung Niederwall 23", "",
    "Anwesend: Frau Uhlmann (Wohnung 3), Herr Schäfer (Wohnung 5), Herr Heidemann (Gewerbe EG)",
    "TOP 1: Fassadenanstrich – beschlossen mit 7 zu 1 Stimmen.",
    "TOP 2: Wirtschaftsplan 2025 – angenommen.",
], soll={})

dok(V + "Seminarunterlagen_DSGVO.pptx", "pptx", "Seminar", [
    ("Datenschutz in der Kanzlei", ["Grundlagen für Mitarbeitende"]),
    ("Beispiel Auskunftsersuchen", ["Max Mustermann verlangt Auskunft nach Art. 15 DSGVO",
                                    "Frist: ein Monat"]),
    ("Löschkonzept", ["Aufbewahrungsfristen beachten (§ 50 BRAO: 6 Jahre)"]),
], soll={})

dok(V + "Telefonliste_intern.txt", "txt", "Telefonliste", [
    "Interne Durchwahlen",
    "",
    "-10  Empfang (Novak)",
    "-11  Dr. Clara Sommer",
    "-12  Bernd Hellweg",
    "-20  Buchhaltung (Krüger)",
    "-21  Sophie Becker (Azubi)",
], soll={})

dok(V + "Jahresplanung_2025.xlsx", "xlsx", "Jahresplanung", {"2025": [
    ["Monat", "Thema", "Verantwortlich"],
    ["Januar", "Inventur Akten", "Novak"],
    ["März", "Datenschutzschulung", "Sommer"],
    ["Juni", "Sommerfest", "Krüger"],
    ["Oktober", "Betriebsausflug", "Hellweg"],
]}, soll={})


def main():
    if len(DOKUMENTE) != 50:
        sys.exit(f"Erwartet 50 Dokumente, es sind {len(DOKUMENTE)}.")
    for d in DOKUMENTE:
        pfad = schreiben(d, ZIEL)
        print(f"  {d.art:5} {os.path.getsize(pfad) / 1024:7.0f} KB  {d.datei}")
    print(f"\n{len(DOKUMENTE)} Dokumente geschrieben nach {ZIEL}")


if __name__ == "__main__":
    main()
