#!/usr/bin/env python3
"""
personensuche.py - in welchen Dateien kommt eine bestimmte Person vor?

WOFUER
------
Eine Kanzlei bekommt ein Auskunftsersuchen (Art. 15 DSGVO) oder einen
Loeschantrag (Art. 17 DSGVO): "Welche Daten haben Sie ueber mich?" Dann
muss jemand herausfinden, in welchen Dokumenten diese Person vorkommt -
in Schreiben, Fristenlisten, gescannten Briefen. Mit der Suche des
Systems dauert das Tage und ist nachweislich unvollstaendig.

WARUM KEINE KI-SUCHE
--------------------
Die normale Lockara-Suche vergleicht Bedeutung. Fuer eine Person ist das
der falsche Weg: "Sabine Wortmann" hat keine Bedeutung, die ein Modell
kennt, und ein aehnlich klingender Name ist ein FALSCHER Treffer. Hier
zaehlt jedes Vorkommen, und nur das. Deshalb vergleicht dieses Modul den
Text exakt - aber mit allen Schreibweisen, die in echten Akten vorkommen:

    "Sabine Wortmann", "Wortmann, Sabine", "S. Wortmann", "Frau Wortmann"
    "Özdemir" = "Oezdemir" = "OZDEMIR"
    "02.07.1980" = "2.7.80" = "1980-07-02" = "2. Juli 1980"
    "Wittekindstraße 30" = "Wittekindstr. 30" = "Wittekindstrasse 30"

WARUM AUS DEM INDEX
-------------------
Der Index enthaelt den gelesenen Text jeder Datei bereits, auch den von
Scans (Texterkennung). Nichts muss neu eingelesen werden; auch tausende
Akten sind in Sekunden durchsucht. Die Kehrseite: Was nicht im Index
steht, wird nicht gefunden. Deshalb nennt das Ergebnis den Stand des
Index, die durchsuchten Ordner und die Dateien, die nicht lesbar waren -
ein Bericht, der Vollstaendigkeit behauptet, muss sagen, wofuer.

STUFEN
------
Ein Nachname allein ist kein Beweis - "Wolf" oder "Koch" stehen in vielen
Dokumenten. Jede Datei bekommt deshalb eine Stufe:

    sicher         voller Name + ein weiteres Merkmal,
                   oder Nachname + ein starkes Merkmal (Anschrift, E-Mail,
                   Telefon, Aktenzeichen ...)
    wahrscheinlich voller Name, oder ein starkes Merkmal allein,
                   oder Nachname + Geburtsdatum
    pruefen        nur Nachname oder nur Geburtsdatum

GELOESCHT WIRD NICHTS. Ob eine Datei geloescht werden darf, haengt an
Aufbewahrungspflichten; das entscheidet ein Mensch.

Dieses Modul kennt keine Oberflaeche und enthaelt keine Saetze fuer
Nutzer. Merkmale und Stufen sind Schluesselwoerter; die Oberflaeche
uebersetzt sie (oberflaeche/i18n.py).
"""

import datetime
import os
import re
import unicodedata
from dataclasses import dataclass, field

from lockara.kern import index as index_modul
from lockara.kern.einstellungen import ueberwachte_ordner
from lockara.kern.pfade import INDEX_FILE


# ---------------------------------------------------------------------------
# Schluesselwoerter (die Oberflaeche uebersetzt sie)
# ---------------------------------------------------------------------------

NAME_VOLL = "name_voll"          # Vor- und Nachname (auch "Nachname, Vorname")
NAME_TEIL = "name_teil"          # Nachname allein oder mit Initial
GEBURTSDATUM = "geburtsdatum"
ANSCHRIFT = "anschrift"
EMAIL = "email"
TELEFON = "telefon"
WEITERE = "weitere"              # Aktenzeichen, Kunden-, Mandantennummer ...
IBAN = "iban"                    # nur Zusatzangabe in gefundenen Dateien

STARKE_MERKMALE = {ANSCHRIFT, EMAIL, TELEFON, WEITERE}

# Reihenfolge, in der Merkmale angezeigt werden: der Name zuerst.
MERKMAL_REIHENFOLGE = (NAME_VOLL, NAME_TEIL, GEBURTSDATUM, ANSCHRIFT, EMAIL, TELEFON, WEITERE, IBAN)


def merkmale_zum_zeigen(merkmale):
    """Die Merkmale einer Datei in Anzeigereihenfolge. "Nachname" entfaellt,
    wenn der volle Name ohnehin gefunden wurde."""
    gezeigt = set(merkmale)
    if NAME_VOLL in gezeigt:
        gezeigt.discard(NAME_TEIL)
    return [m for m in MERKMAL_REIHENFOLGE if m in gezeigt]

SICHER = "sicher"
WAHRSCHEINLICH = "wahrscheinlich"
PRUEFEN = "pruefen"
STUFEN = (SICHER, WAHRSCHEINLICH, PRUEFEN)

# Wie viel Text links und rechts einer Fundstelle gezeigt wird.
AUSSCHNITT_ZEICHEN = 70
# Mehr Fundstellen je Datei braucht weder die Liste noch der Bericht.
MAX_STELLEN_JE_DATEI = 12


@dataclass
class Person:
    """Was ueber die gesuchte Person bekannt ist. Nur name ist Pflicht."""
    name: str
    geburtsdatum: str = ""
    anschrift: str = ""
    email: str = ""
    telefon: str = ""
    weitere: list = field(default_factory=list)


@dataclass
class Fundstelle:
    merkmal: str
    vor: str          # Text vor dem Treffer
    treffer: str      # der Treffer selbst, wie er im Dokument steht
    nach: str         # Text danach


@dataclass
class Fund:
    datei: str
    stufe: str
    merkmale: set
    stellen: list


@dataclass
class Ergebnis:
    person: Person
    funde: list                  # Fund, sortiert: sicher, wahrscheinlich, pruefen
    dateien_durchsucht: int
    nicht_lesbar: list           # Pfade, deren Inhalt nicht gelesen werden konnte
    ordner: list                 # die durchsuchten Ordner
    zeitpunkt: datetime.datetime
    index_stand: datetime.datetime | None
    abgebrochen: bool = False

    def anzahl(self, stufe):
        return sum(1 for f in self.funde if f.stufe == stufe)


class EingabeFehler(ValueError):
    """Eine Angabe ist so nicht verwendbar. args[0] ist ein Schluesselwort
    ("name_fehlt", "geburtsdatum_unlesbar"), die Oberflaeche formuliert."""


# ---------------------------------------------------------------------------
# Text vereinheitlichen
# ---------------------------------------------------------------------------

# Buchstaben, die Unicode nicht in Grundbuchstabe + Akzent zerlegt. Ohne
# "ı" -> "i" waere "Yılmaz" (tuerkisch) nicht "Yilmaz" - und genau so steht
# der Name in Kontoauszuegen, Formularen und Krankmeldungen.
_UMLAUTE = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
            "ı": "i", "ł": "l", "ø": "o", "đ": "d", "ð": "d", "æ": "ae", "œ": "oe", "þ": "th"}


def _zeichen_norm(c):
    """Ein Zeichen in seine Vergleichsform: klein, Umlaute ausgeschrieben,
    Akzente entfernt ("é" -> "e", "ğ" -> "g"). Kann mehrere Zeichen
    ergeben ("ß" -> "ss")."""
    c = c.casefold()
    aus = []
    for z in c:
        if z in _UMLAUTE:
            aus.append(_UMLAUTE[z])
            continue
        zerlegt = unicodedata.normalize("NFKD", z)
        aus.append("".join(b for b in zerlegt if not unicodedata.combining(b)))
    return "".join(aus)


def normalisieren(text):
    """Vergleichsform eines Textes (ohne Karte, fuer Eingaben)."""
    return vergleichsform(text)[0]


def vergleichsform(text):
    """(vereinheitlichter Text, Karte).

    karte[i] ist die Position im Originaltext, aus der Zeichen i der
    Vergleichsform stammt. Damit laesst sich jeder Treffer im Original
    wiederfinden - die Fundstelle soll so aussehen, wie sie im Dokument
    steht, nicht klein geschrieben und mit "oe" statt "ö".

    Zeilenumbrueche und mehrfache Leerzeichen werden zu einem Leerzeichen:
    Texterkennung bricht Namen gern ueber zwei Zeilen um.
    """
    aus = []
    karte = []
    for i, c in enumerate(text):
        if c.isspace():
            if aus and aus[-1] != " ":
                aus.append(" ")
                karte.append(i)
            continue
        for z in _zeichen_norm(c):
            aus.append(z)
            karte.append(i)
    return "".join(aus), karte


# ---------------------------------------------------------------------------
# Suchmuster aus den Angaben bauen
# ---------------------------------------------------------------------------

# Anreden und Titel, die vor einem Namen stehen koennen.
_TITEL = {"herr", "herrn", "frau", "dr", "dr.", "prof", "prof.", "hr", "hr.", "fr", "fr."}
# Namenszusaetze gehoeren zum Nachnamen: "Ursula von der Leyen".
_ZUSAETZE = {"von", "van", "de", "der", "den", "zu", "vom", "zum", "di", "da",
             "del", "la", "le", "ten", "ter", "du"}


def _wortfolge(norm):
    """Regulaerer Ausdruck fuer eine vereinheitlichte Wortfolge: Leerzeichen
    duerfen beliebig viele sein, um Bindestriche darf Leerraum stehen."""
    teile = [re.escape(w) for w in norm.split(" ") if w]
    muster = r"\s+".join(teile)
    return muster.replace(r"\-", r"\s*-\s*")


def name_zerlegen(name):
    """("Sabine", ["sabine"], "wortmann") aus "Sabine Wortmann" oder
    "Wortmann, Sabine". Vornamen und Nachname in Vergleichsform."""
    roh = (name or "").strip()
    if not roh:
        raise EingabeFehler("name_fehlt")
    if "," in roh:
        nach, _, vor = roh.partition(",")
        vornamen = normalisieren(vor).split()
        nachname = [w for w in normalisieren(nach).split() if w not in _TITEL]
    else:
        woerter = normalisieren(roh).split()
        woerter = [w for w in woerter if w not in _TITEL]
        if not woerter:
            raise EingabeFehler("name_fehlt")
        nachname = [woerter.pop()]
        # Zusaetze vor dem Nachnamen gehoeren dazu: "von der Leyen"
        while woerter and woerter[-1] in _ZUSAETZE:
            nachname.insert(0, woerter.pop())
        vornamen = woerter
    vornamen = [v for v in vornamen if v not in _TITEL]
    if not nachname:
        raise EingabeFehler("name_fehlt")
    return vornamen, " ".join(nachname)


# Namenszusaetze werden gern abgekuerzt: "H.-P. v. d. Heide".
_ZUSATZ_KUERZEL = {"von": "v", "van": "v", "der": "d", "den": "d", "de": "d", "zu": "z", "vom": "v"}


def _nachnamensmuster(nachname):
    """Regulaerer Ausdruck fuer den Nachnamen samt Zusaetzen und
    Doppelnamen. Zusaetze duerfen abgekuerzt sein ("v. d.")."""
    teile = []
    for wort in nachname.split(" "):
        if wort in _ZUSATZ_KUERZEL:
            teile.append(rf"(?:{re.escape(wort)}|{_ZUSATZ_KUERZEL[wort]}\.)")
        else:
            teile.append(re.escape(wort).replace(r"\-", r"\s*-\s*"))
    return r"\s*".join(teile)


def _vornamensmuster(vornamen):
    """Alternativen fuer den Rufnamen. Jeder Vorname zaehlt ("Hans Peter
    Mueller" ist auch "Peter Mueller"); bei "Hans-Peter" auch "Hans Peter"
    und "Hans"."""
    muster = []
    for v in vornamen:
        teile = [re.escape(t) for t in v.split("-") if t]
        if len(teile) > 1:
            muster.append(r"[\s-]*".join(teile))
            muster.append(teile[0])
        elif teile:
            muster.append(teile[0])
    return "|".join(muster)


def _namensmuster(name):
    """(Muster fuer den vollen Namen oder None, Muster fuer den Nachnamen)."""
    vornamen, nachname = name_zerlegen(name)
    n = _nachnamensmuster(nachname)
    nur_nachname = re.compile(rf"(?<!\w){n}(?!\w)")
    if not vornamen:
        return None, nur_nachname

    vor = _vornamensmuster(vornamen)
    initialen = "|".join(sorted({re.escape(v[0]) for v in vornamen}))
    voll = re.compile(
        # Vorname [weitere Vornamen oder Initialen] Nachname
        rf"(?<!\w)(?:{vor})\s+(?:(?:\w\.|\w+)\s+){{0,2}}{n}(?!\w)"
        # Nachname, Vorname - und "YILMAZ MEHMET" ohne Komma, wie in
        # Kontoauszuegen und Bankformularen
        rf"|(?<!\w){n}\s*,?\s*(?:{vor})(?![\w-])"
    )
    # Initial + Nachname ("S. Wortmann", "H.-P. v. d. Heide", "Wortmann, S.")
    # ist kein voller Name - es gibt viele S. Wortmanns -, aber mehr als der
    # Nachname allein.
    teil = re.compile(
        rf"(?<!\w)(?:{initialen})\.(?:\s*-?\s*\w\.)?\s*{n}(?!\w)"
        rf"|(?<!\w){n}\s*,\s*(?:{initialen})\."
        rf"|(?<!\w){n}(?!\w)"
    )
    return voll, teil


_MONATE = [
    ("januar", "jan", "january"), ("februar", "feb", "february"),
    ("maerz", "mrz", "mar", "march"), ("april", "apr"), ("mai", "may"),
    ("juni", "jun", "june"), ("juli", "jul", "july"), ("august", "aug"),
    ("september", "sep", "sept"), ("oktober", "okt", "oct", "october"),
    ("november", "nov"), ("dezember", "dez", "dec", "december"),
]


def datum_lesen(text, heute=None):
    """datetime.date aus "02.07.1980", "2.7.80", "1980-07-02" - oder Fehler."""
    text = (text or "").strip()
    heute = heute or datetime.date.today()
    m = re.fullmatch(r"(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{2}|\d{4})", text)
    if m:
        tag, monat, jahr = int(m.group(1)), int(m.group(2)), m.group(3)
    else:
        m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
        if not m:
            raise EingabeFehler("geburtsdatum_unlesbar")
        jahr, monat, tag = m.group(1), int(m.group(2)), int(m.group(3))
    jahr = int(jahr)
    if jahr < 100:
        # Zweistellig: das letzte passende Jahrhundert, nie in der Zukunft
        jahr += 2000 if 2000 + jahr <= heute.year else 1900
    try:
        return datetime.date(jahr, monat, tag)
    except ValueError:
        raise EingabeFehler("geburtsdatum_unlesbar")


def _datumsmuster(datum):
    d, m, j = datum.day, datum.month, datum.year
    jahr = rf"(?:{j}|{j % 100:02d})"
    monat = "|".join(re.escape(x) for x in _MONATE[m - 1])
    return re.compile(
        rf"(?<!\d)0?{d}\s*[./]\s*0?{m}\s*[./]\s*{jahr}(?!\d)"
        rf"|(?<!\d){j}-{m:02d}-{d:02d}(?!\d)"
        rf"|(?<!\d)0?{d}\.?\s+(?:{monat})\.?\s+{jahr}(?!\d)"
    )


def _anschriftsmuster(anschrift):
    """Muster fuer Strasse + Hausnummer. Postleitzahl und Ort allein sagen
    nichts ueber eine Person und werden nicht gesucht."""
    zeile = anschrift.split(",")[0].split("\n")[0]
    norm = normalisieren(zeile).strip()
    m = re.fullmatch(r"(.+?)\s*(\d+\s*[a-z]?)", norm)
    if not m:
        return None
    strasse, nummer = m.group(1).strip(), m.group(2).replace(" ", "")
    # "Straße", "Strasse", "Str." und "Str" sind dasselbe - im Dokument
    # kann jede Form stehen, egal welche eingegeben wurde.
    endung = ""
    gekuerzt = re.sub(r"\s*(?:strasse|str\.?)$", "", strasse)
    if gekuerzt != strasse:
        endung = r"\s*(?:strasse|str\.?)" if strasse[len(gekuerzt)] == " " else r"(?:strasse|str\.?)"
        strasse = gekuerzt
    s = _wortfolge(strasse) if strasse else ""
    if nummer[-1].isalpha():
        nr = re.escape(nummer[:-1]) + r"\s*" + re.escape(nummer[-1])
    else:
        nr = re.escape(nummer)
    return re.compile(rf"(?<!\w){s}{endung}\s*{nr}(?![\d\w])")


def _telefon_ziffern(text):
    """Nur die Ziffern, mit einheitlicher Vorwahl: +49 / 0049 -> 0.
    "+49 (0)521 ..." - die eingeklammerte Null faellt weg."""
    text = re.sub(r"\(\s*0\s*\)", "", text)
    ziffern = re.sub(r"\D", "", text)
    if text.strip().startswith("+"):
        if ziffern.startswith("49"):
            return "0" + ziffern[2:]
        return "00" + ziffern
    if ziffern.startswith("0049"):
        return "0" + ziffern[4:]
    return ziffern


_TELEFON_KANDIDAT = re.compile(r"(?:\+\s?\d{1,3}|\(?0)[\d\s/().-]{5,}\d")
_IBAN_KANDIDAT = re.compile(r"(?<!\w)[a-z]{2}\d{2}(?:\s?[a-z0-9]){11,30}(?!\w)")


def _iban_gueltig(roh):
    iban = re.sub(r"\s", "", roh).upper()
    if not 15 <= len(iban) <= 34:
        return False
    umgestellt = iban[4:] + iban[:4]
    try:
        zahl = int("".join(str(int(c, 36)) for c in umgestellt))
    except ValueError:
        return False
    return zahl % 97 == 1


def _weitere_muster(begriff):
    norm = normalisieren(begriff).strip()
    if not norm:
        return None
    # Woerter und Satzzeichen einzeln: "2 Ca 311/24" soll auch
    # "2 Ca 311 / 24" treffen - Texterkennung setzt gern Leerzeichen.
    teile = []
    for w in re.findall(r"\w+|[^\w\s]", norm):
        if len(w) > 4 and any(z.isdigit() for z in w):
            # Lange Nummern werden in Dokumenten gern gegliedert:
            # Steuer-ID "12 345 678 901", IBAN "DE12 4805 ..." - eingegeben
            # werden sie oft am Stueck. Zwischen den Zeichen darf Leerraum sein.
            teile.append(r"\s?".join(re.escape(z) for z in w))
        else:
            teile.append(re.escape(w))
    muster = r"\s*".join(teile)
    return re.compile(rf"(?<!\w){muster}(?!\w)")


@dataclass
class _Suchplan:
    muster: list          # (merkmal, regex)
    telefon: str          # Ziffernform oder ""


def suchplan(person):
    """Baut alle Muster einmal - nicht je Textabschnitt neu.

    Wirft EingabeFehler bei fehlendem Namen oder unlesbarem Datum, BEVOR
    der Index geladen wird."""
    voll, teil = _namensmuster(person.name)
    muster = []
    if voll is not None:
        muster.append((NAME_VOLL, voll))
    muster.append((NAME_TEIL, teil))
    if person.geburtsdatum.strip():
        muster.append((GEBURTSDATUM, _datumsmuster(datum_lesen(person.geburtsdatum))))
    if person.anschrift.strip():
        a = _anschriftsmuster(person.anschrift)
        if a is not None:
            muster.append((ANSCHRIFT, a))
    if person.email.strip():
        e = re.escape(normalisieren(person.email).strip())
        muster.append((EMAIL, re.compile(rf"(?<![\w.]){e}(?!\w)")))
    for begriff in person.weitere:
        w = _weitere_muster(begriff)
        if w is not None:
            muster.append((WEITERE, w))
    telefon = _telefon_ziffern(person.telefon) if person.telefon.strip() else ""
    if len(telefon) < 6:
        telefon = ""
    return _Suchplan(muster, telefon)


# ---------------------------------------------------------------------------
# Durchsuchen
# ---------------------------------------------------------------------------

def _ausschnitt(original, karte, start, ende, merkmal):
    a = karte[start]
    b = karte[ende - 1] + 1
    vor = original[max(0, a - AUSSCHNITT_ZEICHEN):a]
    nach = original[b:b + AUSSCHNITT_ZEICHEN]
    eng = lambda s: re.sub(r"\s+", " ", s)
    vor, nach = eng(vor), eng(nach)
    if a - AUSSCHNITT_ZEICHEN > 0:
        vor = "… " + vor.lstrip()
    if b + AUSSCHNITT_ZEICHEN < len(original):
        nach = nach.rstrip() + " …"
    return Fundstelle(merkmal, vor, eng(original[a:b]), nach)


def _sieht_aus_wie_name(original, karte, start, ende):
    """Ein Nachname steht im Dokument gross geschrieben. "klein" oder
    "wolf" mitten im Satz ist kein Herr Klein und keine Frau Wolf.

    Geprueft wird das LETZTE Wort des Treffers: bei "von der Heide" ist das
    "Heide" - der Zusatz "von" ist klein, und das ist richtig so."""
    treffer = original[karte[start]:karte[ende - 1] + 1]
    woerter = [w for w in re.split(r"[\s.,-]+", treffer) if w]
    return bool(woerter) and woerter[-1][0].isupper()


def abschnitt_pruefen(text, plan):
    """Alle Fundstellen in einem Textabschnitt: Liste von Fundstelle."""
    norm, karte = vergleichsform(text)
    stellen = []
    belegt = []          # Bereiche, die schon als voller Name zaehlen
    for merkmal, regex in plan.muster:
        for m in regex.finditer(norm):
            s, e = m.span()
            if s == e:
                continue
            if merkmal == NAME_TEIL:
                if any(s < b and e > a for a, b in belegt):
                    continue
                if not _sieht_aus_wie_name(text, karte, s, e):
                    continue
            if merkmal == NAME_VOLL:
                belegt.append((s, e))
            stellen.append(_ausschnitt(text, karte, s, e, merkmal))
    if plan.telefon:
        for m in _TELEFON_KANDIDAT.finditer(norm):
            if _telefon_ziffern(m.group()) == plan.telefon:
                stellen.append(_ausschnitt(text, karte, m.start(), m.end(), TELEFON))
    return stellen


def ibans_in(text):
    """Gueltige IBANs in einem Text (Pruefziffer stimmt) als Fundstellen."""
    norm, karte = vergleichsform(text)
    return [_ausschnitt(text, karte, m.start(), m.end(), IBAN)
            for m in _IBAN_KANDIDAT.finditer(norm) if _iban_gueltig(m.group())]


def stufe_fuer(merkmale):
    """Die Stufe einer Datei aus den gefundenen Merkmalen - oder None."""
    m = set(merkmale) - {IBAN}
    if NAME_VOLL in m and (m - {NAME_VOLL, NAME_TEIL}):
        return SICHER
    if NAME_TEIL in m and (m & STARKE_MERKMALE):
        return SICHER
    if NAME_VOLL in m or (m & STARKE_MERKMALE):
        return WAHRSCHEINLICH
    if NAME_TEIL in m and GEBURTSDATUM in m:
        return WAHRSCHEINLICH
    if m:
        return PRUEFEN
    return None


def _index_stand():
    try:
        return datetime.datetime.fromtimestamp(os.path.getmtime(INDEX_FILE))
    except OSError:
        return None


def durchsuchen(person, soll_abbrechen=None, melden=None):
    """Durchsucht den gespeicherten Index nach der Person.

    soll_abbrechen: Funktion ohne Argumente, True bricht ab (Ergebnis ist
                    dann unvollstaendig und als abgebrochen markiert).
    melden:         Funktion(n, gesamt) fuer eine Fortschrittsanzeige.

    Darf nicht im Tk-Hauptthread laufen: der Index kann mehrere hundert MB
    gross sein (siehe ARCHITEKTUR.md).
    """
    plan = suchplan(person)
    zeitpunkt = datetime.datetime.now()

    eintraege = index_modul.nur_gueltige_eintraege(index_modul.lade_bestehenden_index())

    je_datei = {}
    nicht_lesbar = set()
    for e in eintraege:
        if e.get("ohne_inhalt"):
            nicht_lesbar.add(e["datei"])
            continue
        je_datei.setdefault(e["datei"], []).append(e.get("text") or "")

    funde = []
    gesamt = len(je_datei)
    abgebrochen = False
    for n, (pfad, abschnitte) in enumerate(je_datei.items(), 1):
        if soll_abbrechen and soll_abbrechen():
            abgebrochen = True
            break
        stellen = []
        gesehen = set()
        for text in abschnitte:
            for s in abschnitt_pruefen(text, plan):
                # Abschnitte ueberlappen sich (dateien.ABSCHNITT_UEBERLAPPUNG);
                # dieselbe Stelle soll nicht doppelt erscheinen.
                schluessel = (s.merkmal, normalisieren(s.vor[-30:] + s.treffer + s.nach[:30]))
                if schluessel in gesehen:
                    continue
                gesehen.add(schluessel)
                stellen.append(s)
        merkmale = {s.merkmal for s in stellen}
        stufe = stufe_fuer(merkmale)
        if stufe is not None:
            for text in abschnitte:
                for s in ibans_in(text):
                    schluessel = (IBAN, normalisieren(s.treffer))
                    if schluessel not in gesehen:
                        gesehen.add(schluessel)
                        stellen.append(s)
            merkmale = {s.merkmal for s in stellen}
            # Wichtigste Stellen zuerst: voller Name, starke Merkmale, Rest
            rang = {NAME_VOLL: 0, ANSCHRIFT: 1, EMAIL: 1, TELEFON: 1, WEITERE: 1,
                    GEBURTSDATUM: 2, NAME_TEIL: 3, IBAN: 4}
            stellen.sort(key=lambda s: rang.get(s.merkmal, 9))
            funde.append(Fund(pfad, stufe, merkmale, stellen[:MAX_STELLEN_JE_DATEI]))
        if melden and (n % 200 == 0 or n == gesamt):
            melden(n, gesamt)

    reihenfolge = {s: i for i, s in enumerate(STUFEN)}
    funde.sort(key=lambda f: (reihenfolge[f.stufe], f.datei.lower()))

    return Ergebnis(
        person=person,
        funde=funde,
        dateien_durchsucht=gesamt if not abgebrochen else n - 1,
        nicht_lesbar=sorted(nicht_lesbar),
        ordner=list(ueberwachte_ordner()),
        zeitpunkt=zeitpunkt,
        index_stand=_index_stand(),
        abgebrochen=abgebrochen,
    )
