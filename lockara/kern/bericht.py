#!/usr/bin/env python3
"""
bericht.py - das Ergebnis einer Personensuche als PDF.

Der Bericht ist ein Nachweis fuer die Akte: Wann wurde wonach gesucht,
wo, mit welchem Ergebnis - und was konnte NICHT durchsucht werden. Eine
Kanzlei legt ihn zum Auskunftsersuchen; er muss auch in einem Jahr noch
verstaendlich sein, ohne dass jemand Lockara kennt.

Alle Saetze kommen von der Oberflaeche (texte, aus i18n.py) - der Kern
formuliert nichts selbst (siehe docs/ARCHITEKTUR.md). Benoetigte
Schluessel stehen in TEXT_SCHLUESSEL.

Schrift: eine TrueType-Schrift des Systems (plattform.schriftdateien),
damit auch "Yılmaz" oder "Dvořák" richtig erscheinen. Fehlt sie, faellt
der Bericht auf Helvetica zurueck; das kann nur Westeuropaeisch, ist aber
besser als gar kein Bericht.
"""

import os
from xml.sax.saxutils import escape

from lockara import plattform
from lockara.kern import personensuche as ps

TEXT_SCHLUESSEL = (
    "titel", "erstellt", "gesucht", "angaben", "ordner", "dateien",
    "index_stand", "programm", "lizenznehmer", "zusammenfassung",
    "keine_funde", "abgebrochen", "nicht_lesbar_titel", "nicht_lesbar_text",
    "hinweis_titel", "hinweis_text", "seite", "weitere_stellen", "datum_format",
    "merkmale",
) + tuple(f"stufe_{s}" for s in ps.STUFEN) + tuple(f"stufe_{s}_erklaerung" for s in ps.STUFEN)

# So viele Fundstellen je Datei stehen im Bericht; der Rest wird gezaehlt.
STELLEN_IM_BERICHT = 3

_AKZENT = "#c0392b"     # das Aktenrot der App
_GRAU = "#5f6b76"
_STUFENFARBE = {ps.SICHER: "#2e7d32", ps.WAHRSCHEINLICH: "#ef6c00", ps.PRUEFEN: "#5f6b76"}


def _schriften():
    """(normal, fett) als reportlab-Schriftnamen."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    dateien = plattform.schriftdateien()
    if dateien:
        try:
            if "LockaraNormal" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("LockaraNormal", dateien[0]))
                pdfmetrics.registerFont(TTFont("LockaraFett", dateien[1]))
            return "LockaraNormal", "LockaraFett"
        except Exception as e:
            print(f"[Bericht] Systemschrift nicht nutzbar, nehme Helvetica: {e}")
    return "Helvetica", "Helvetica-Bold"


def angaben_liste(person, texte_merkmale):
    """[(Bezeichnung, Wert)] der eingegebenen Merkmale ausser dem Namen."""
    zeilen = []
    for schluessel, wert in ((ps.GEBURTSDATUM, person.geburtsdatum), (ps.ANSCHRIFT, person.anschrift),
                             (ps.EMAIL, person.email), (ps.TELEFON, person.telefon)):
        if wert.strip():
            zeilen.append((texte_merkmale[schluessel], wert.strip()))
    for w in person.weitere:
        if w.strip():
            zeilen.append((texte_merkmale[ps.WEITERE], w.strip()))
    return zeilen


def schreiben(pfad, ergebnis, texte, merkmal_namen, version, lizenznehmer=""):
    """Schreibt den Bericht nach pfad (atomar: erst .tmp, dann ersetzen).

    texte:          {Schluessel: Text} mit allen TEXT_SCHLUESSEL
    merkmal_namen:  {Merkmal-Schluessel: Bezeichnung}, z. B. {"anschrift": "Anschrift"}
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)

    fehlend = [k for k in TEXT_SCHLUESSEL if k not in texte]
    if fehlend:
        raise KeyError(f"Bericht: Texte fehlen: {', '.join(fehlend)}")

    normal, fett = _schriften()
    def stil(**k):
        return ParagraphStyle("x", **{"fontName": normal, "fontSize": 9.5, "leading": 13, **k})
    s_titel = stil(fontName=fett, fontSize=17, leading=21, spaceAfter=2)
    s_marke = stil(fontName=fett, fontSize=9, textColor=colors.HexColor(_AKZENT))
    # keepWithNext: eine Ueberschrift steht nie allein unten auf der Seite
    s_h2 = stil(fontName=fett, fontSize=12.5, leading=16, spaceBefore=12, spaceAfter=3, keepWithNext=1)
    s_erkl = stil(fontSize=8.5, leading=11, textColor=colors.HexColor(_GRAU), keepWithNext=1)
    s_text = stil()
    s_klein = stil(fontSize=8.5, leading=11, textColor=colors.HexColor(_GRAU))
    s_datei = stil(fontName=fett, fontSize=10, leading=13)
    s_stelle = stil(fontSize=8.8, leading=11.5, leftIndent=8)
    s_zelle_k = stil(fontSize=9, textColor=colors.HexColor(_GRAU))

    e = lambda s: escape(str(s))
    datum = lambda d: d.strftime(texte["datum_format"]) if d else "–"
    stufe_text = lambda s: texte[f"stufe_{s}"]

    teile = []
    teile.append(Paragraph("LOCKARA", s_marke))
    teile.append(Paragraph(e(texte["titel"]), s_titel))
    teile.append(Spacer(1, 4 * mm))

    # --- Rahmendaten ---
    zeilen = [
        (texte["erstellt"], datum(ergebnis.zeitpunkt)),
        (texte["gesucht"], ergebnis.person.name.strip()),
    ]
    for bez, wert in angaben_liste(ergebnis.person, merkmal_namen):
        zeilen.append((bez, wert))
    zeilen += [
        (texte["ordner"], "\n".join(ergebnis.ordner) or "–"),
        (texte["dateien"], f"{ergebnis.dateien_durchsucht:,}".replace(",", ".")),
        (texte["index_stand"], datum(ergebnis.index_stand)),
        (texte["programm"], f"Lockara {version}"),
    ]
    if lizenznehmer:
        zeilen.append((texte["lizenznehmer"], lizenznehmer))
    tabelle = Table(
        [[Paragraph(e(a), s_zelle_k), Paragraph(e(b).replace("\n", "<br/>"), s_text)] for a, b in zeilen],
        colWidths=[42 * mm, None])
    tabelle.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#d9dde1")),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    teile.append(tabelle)
    teile.append(Spacer(1, 5 * mm))

    # --- Zusammenfassung ---
    teile.append(Paragraph(e(texte["zusammenfassung"].format(
        gesamt=len(ergebnis.funde), sicher=ergebnis.anzahl(ps.SICHER),
        wahrscheinlich=ergebnis.anzahl(ps.WAHRSCHEINLICH), pruefen=ergebnis.anzahl(ps.PRUEFEN))), s_h2))
    if ergebnis.abgebrochen:
        teile.append(Paragraph(f'<font color="{_AKZENT}">{e(texte["abgebrochen"])}</font>', s_text))
    if not ergebnis.funde:
        teile.append(Paragraph(e(texte["keine_funde"]), s_text))

    # --- Funde je Stufe ---
    for stufe in ps.STUFEN:
        funde = [f for f in ergebnis.funde if f.stufe == stufe]
        if not funde:
            continue
        farbe = _STUFENFARBE[stufe]
        teile.append(Paragraph(f'<font color="{farbe}">●</font> {e(stufe_text(stufe))} ({len(funde)})', s_h2))
        teile.append(Paragraph(e(texte[f"stufe_{stufe}_erklaerung"]), s_erkl))
        teile.append(Spacer(1, 2 * mm))
        for f in funde:
            block = [Paragraph(e(os.path.basename(f.datei)), s_datei),
                     Paragraph(e(os.path.dirname(f.datei)), s_klein)]
            block.append(Paragraph(e(texte["merkmale"]) + " " + e(", ".join(
                merkmal_namen[m] for m in ps.merkmale_zum_zeigen(f.merkmale))), s_klein))
            for s in f.stellen[:STELLEN_IM_BERICHT]:
                block.append(Paragraph(f"{e(s.vor)}<b><font name='{fett}'>{e(s.treffer)}</font></b>{e(s.nach)}", s_stelle))
            rest = len(f.stellen) - STELLEN_IM_BERICHT
            if rest > 0:
                block.append(Paragraph(e(texte["weitere_stellen"].format(n=rest)), s_klein))
            block.append(Spacer(1, 3 * mm))
            teile.append(KeepTogether(block))

    # --- Nicht durchsuchbar ---
    if ergebnis.nicht_lesbar:
        teile.append(Paragraph(e(texte["nicht_lesbar_titel"]) + f" ({len(ergebnis.nicht_lesbar)})", s_h2))
        teile.append(Paragraph(e(texte["nicht_lesbar_text"]), s_klein))
        for p in ergebnis.nicht_lesbar:
            teile.append(Paragraph(e(p), s_stelle))

    # --- Hinweis ---
    teile.append(Paragraph(e(texte["hinweis_titel"]), s_h2))
    teile.append(Paragraph(e(texte["hinweis_text"]), s_klein))

    def fusszeile(leinwand, doc):
        leinwand.saveState()
        leinwand.setFont(normal, 8)
        leinwand.setFillColor(colors.HexColor(_GRAU))
        leinwand.drawString(18 * mm, 10 * mm, f"Lockara · {ergebnis.person.name.strip()} · {datum(ergebnis.zeitpunkt)}")
        leinwand.drawRightString(A4[0] - 18 * mm, 10 * mm, texte["seite"].format(n=doc.page))
        leinwand.restoreState()

    temp = pfad + ".tmp"
    doc = SimpleDocTemplate(temp, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=18 * mm,
                            title=texte["titel"], author="Lockara")
    doc.build(teile, onFirstPage=fusszeile, onLaterPages=fusszeile)
    os.replace(temp, pfad)
    return pfad
