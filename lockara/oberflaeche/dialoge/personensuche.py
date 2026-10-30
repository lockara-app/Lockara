#!/usr/bin/env python3
"""
dialoge/personensuche.py - Fenster der Personensuche (DSGVO).

Eingabe der Merkmale, Suche im Hintergrund, Trefferliste nach Stufen und
der PDF-Bericht. Gerechnet wird in kern/personensuche.py, der Bericht
entsteht in kern/bericht.py - hier wird nur angezeigt.

Die Eingaben werden NIRGENDS gespeichert, auch nicht im Suchverlauf: Name
und Geburtsdatum eines Mandanten haben in einer Verlaufsdatei nichts zu
suchen.

Ohne gueltige Lizenz zeigt das Fenster statt des Formulars, wofuer die
Funktion da ist, einen Knopf fuer die Anfrage einer Testlizenz per E-Mail
und ein Feld fuer den Lizenzcode, der darauf zurueckkommt (kern/lizenz.py,
werkzeuge/lizenz_ausstellen.py --test).

GESTALTUNG (30.10.2026)
-----------------------
Vorher war jeder Knopf gleich laut: "Suchen", "Bericht" und das "Oeffnen"
in jeder einzelnen Trefferzeile waren alle aktenrot. Jetzt traegt immer
nur EIN Knopf den Akzent - der naechste Schritt: vor der Suche "Suchen",
danach "Bericht als PDF speichern". Alles andere ist umrandet oder nur
Text.

Die Trefferflaeche hat fuer jeden Zustand eine eigene Ansicht (noch keine
Suche, laeuft mit Fortschritt, keine Fundstellen, kein Index, Fehler),
statt einer leeren grauen Flaeche. Eingabefehler stehen am Feld, nicht in
einer Statuszeile. Die Fundstelle im Ausschnitt ist gelb markiert wie mit
einem Textmarker - dasselbe Bild wie auf lockara.de.
"""

import datetime
import os
import re
import sys
import threading
import urllib.parse
import webbrowser
from tkinter import filedialog

import customtkinter as ctk

from lockara import plattform, version
from lockara.kern import bericht, lizenz
from lockara.kern.rueckmeldung import RUECKMELDUNG_ADRESSE
from lockara.kern import personensuche as ps
from lockara.oberflaeche import farben
from lockara.oberflaeche.i18n import aktuelle_sprache, t

# So viele Dateien zeigt die Liste; der Bericht enthaelt immer alle.
# CustomTkinter wird bei einigen hundert Zeilen spuerbar langsam.
MAX_ZEILEN = 200

# ---------------------------------------------------------------------------
# Schrift und Farben
# ---------------------------------------------------------------------------
# Die Systemschrift (San Francisco / Segoe UI). Kommt aus farben.SCHRIFT,
# sobald es das dort gibt; bis dahin dieselbe Auswahl hier.
if sys.platform == "darwin":
    _SYSTEM, _MONO = ".AppleSystemUIFont", "Menlo"
elif sys.platform == "win32":
    _SYSTEM, _MONO = "Segoe UI", "Consolas"
else:
    _SYSTEM, _MONO = "Helvetica", "Courier"
_SCHRIFT = getattr(farben, "SCHRIFT", _SYSTEM)

_TEXT = farben.TEXT
_GRAU = farben.GEDAEMPFT
_LINIE = farben.LINIE
_KARTE = getattr(farben, "KARTE", ("#ffffff", "#252a32"))
_RAND = getattr(farben, "NEBENKNOPF_RAND", ("#d5d4ce", "#3d434d"))
# Eingabefelder auf der Karte: im dunklen Modus eine Stufe TIEFER als die
# Karte. farben.FELD hat dort fast denselben Ton wie KARTE - die Felder
# waren auf der Karte nicht mehr zu sehen.
_FELD = ("#ffffff", "#1a1d23")

# Ampel der Stufen - gedeckt, damit sie neben dem Aktenrot nicht schreit.
_STUFENFARBE = {
    ps.SICHER: ("#2f7d4a", "#5fbf7f"),
    ps.WAHRSCHEINLICH: ("#b86a00", "#e3a13d"),
    ps.PRUEFEN: ("#8a92a0", "#8f98a6"),
}
_FEHLER = ("#b3261e", "#f08a80")
_ERFOLG = ("#2f7d4a", "#5fbf7f")
_HINWEIS_TEXT = getattr(farben, "HINWEIS", ("#9a5300", "#e3a13d"))
_HINWEIS_GRUND = ("#fbf3e6", "#2c261d")

# Textmarker fuer die Fundstelle. tk.Text kennt keine Farbpaare, daher
# wird beim Erzeugen nach Hell/Dunkel gewaehlt.
_MARKER = {"Light": ("#ffe36e", "#2c3340"), "Dark": ("#6b5a12", "#fff4c2")}


def _schrift(groesse, fett=False):
    return (_SCHRIFT, groesse, "bold") if fett else (_SCHRIFT, groesse)


def _knopf(eltern, text, command, art="primaer", **kw):
    """Drei Gewichte: primaer (Akzent), neben (umrandet), text (nur Schrift)."""
    kw.setdefault("height", 32)
    kw.setdefault("font", _schrift(13, art == "primaer"))
    if art == "neben":
        kw.update(fg_color="transparent", border_width=1, border_color=_RAND,
                  text_color=_TEXT, hover_color=farben.MARKIERT)
    elif art == "text":
        kw.update(fg_color="transparent", text_color=_GRAU, hover_color=farben.MARKIERT)
        kw.setdefault("width", 0)
    return ctk.CTkButton(eltern, text=text, command=command, **kw)


def _knopf_art(knopf, art):
    """Schaltet einen Knopf zwischen primaer und neben um."""
    if art == "primaer":
        knopf.configure(fg_color=farben.AKZENT, hover_color=farben.AKZENT_HOVER, border_width=0,
                        text_color=farben.AUF_AKZENT, font=_schrift(13, True))
    else:
        knopf.configure(fg_color="transparent", hover_color=farben.MARKIERT, border_width=1,
                        border_color=_RAND, text_color=_TEXT, font=_schrift(13))


def _punkt(eltern, farbe, groesse=8):
    """Farbiger Punkt fuer eine Stufe - gezeichnet, kein Schriftzeichen."""
    return ctk.CTkFrame(eltern, width=groesse, height=groesse, corner_radius=groesse // 2,
                        fg_color=farbe)


def _zahl(n):
    """1284 -> "1.284" (de) bzw. "1,284" (en)."""
    text = f"{n:,}"
    return text.replace(",", ".") if aktuelle_sprache() == "de" else text


def _kurzpfad(pfad):
    heim = os.path.expanduser("~")
    return "~" + pfad[len(heim):] if pfad.startswith(heim + os.sep) else pfad


def merkmal_namen():
    return {m: t(f"person.trait_{m}") for m in (
        ps.NAME_VOLL, ps.NAME_TEIL, ps.GEBURTSDATUM, ps.ANSCHRIFT,
        ps.EMAIL, ps.TELEFON, ps.WEITERE, ps.IBAN)}


def bericht_texte():
    """Die Saetze fuer kern/bericht.py in der eingestellten Sprache."""
    texte = {
        "titel": t("report.title"), "erstellt": t("report.created"),
        "gesucht": t("report.searched_for"), "angaben": t("report.details"),
        "ordner": t("report.folders"), "dateien": t("report.files"),
        "index_stand": t("report.index_date"), "programm": t("report.program"),
        "lizenznehmer": t("report.licensee"), "zusammenfassung": t("report.summary"),
        "keine_funde": t("report.no_results"), "abgebrochen": t("report.cancelled"),
        "nicht_lesbar_titel": t("report.unreadable_title"),
        "nicht_lesbar_text": t("report.unreadable_text"),
        "hinweis_titel": t("report.note_title"), "hinweis_text": t("report.note_text"),
        "seite": t("report.page"), "weitere_stellen": t("report.more_spots"),
        "datum_format": t("report.date_format"), "merkmale": t("report.traits"),
    }
    for s in ps.STUFEN:
        texte[f"stufe_{s}"] = t(f"person.level_{s}")
        texte[f"stufe_{s}_erklaerung"] = t(f"person.level_{s}_explain")
    return texte


def dateiname_fuer_bericht(person, heute=None):
    heute = heute or datetime.date.today()
    _, nachname = ps.name_zerlegen(person.name)
    sauber = re.sub(r"[^\w-]+", "_", nachname).strip("_") or "Person"
    return t("person.report_filename", name=sauber.title(), datum=heute.isoformat())


def oeffnen(app):
    """Oeffnet das Fenster - oder holt es nach vorn, wenn es schon offen ist."""
    vorhanden = getattr(app, "personensuche_fenster", None)
    if vorhanden is not None and vorhanden.winfo_exists():
        vorhanden.deiconify()
        vorhanden.lift()
        vorhanden.focus_force()
        return

    app.attributes("-topmost", False)
    top = ctk.CTkToplevel(app)
    top.title(t("person.window_title"))
    top.geometry("800x820")
    top.minsize(640, 560)
    top.attributes("-topmost", True)
    app.nebenfenster_anmelden(top)
    app.personensuche_fenster = top

    stand = lizenz.status()
    if not stand.lizenziert:
        _gesperrt(app, top, stand)
        return
    _freigeschaltet(app, top, stand)


def _datum(d):
    return d.strftime("%d.%m.%Y") if d else ""


def _freigeschaltet(app, top, stand):
    name = stand.daten.get("lizenznehmer", "")
    hinweis = ""
    if stand.ist_test:
        hinweis = t("person.trial_active", name=name, bis=_datum(stand.gueltig_bis))
        # Steht auch im Bericht: ein Nachweis aus der Testphase soll als
        # solcher erkennbar bleiben.
        name = t("report.trial_suffix", name=name, bis=_datum(stand.gueltig_bis))
    _Personensuche(app, top, name, hinweis, stand.gueltig_bis if stand.ist_test else None)


def anfrage_link():
    """mailto-Link fuer die Anfrage einer Testlizenz."""
    return (f"mailto:{RUECKMELDUNG_ADRESSE}"
            f"?subject={urllib.parse.quote(t('person.mail_subject'))}"
            f"&body={urllib.parse.quote(t('person.mail_body'))}")


def _gesperrt(app, top, stand):
    """Ohne Lizenz: wofuer die Funktion da ist, wie man sie testet, und ein
    Feld fuer den Lizenzcode aus der E-Mail."""
    # Ohne Trefferliste braucht das Fenster nicht die volle Hoehe.
    top.geometry("720x680")
    rahmen = ctk.CTkFrame(top, fg_color="transparent")
    rahmen.pack(fill="both", expand=True, padx=32, pady=(32, 24))

    ctk.CTkLabel(rahmen, text=t("person.locked_heading"), font=_schrift(22, True), anchor="w"
                 ).pack(fill="x")
    # Nur der erste Absatz - der zweite (Testlizenz) steht unten in der Karte.
    ctk.CTkLabel(rahmen, text=t("person.locked_text").split("\n\n")[0], font=_schrift(13),
                 text_color=_GRAU, justify="left", anchor="w", wraplength=640
                 ).pack(fill="x", pady=(8, 20))

    if stand.ist_test and stand.art == "abgelaufen":
        _hinweisleiste(rahmen, t("person.trial_expired", bis=_datum(stand.gueltig_bis))
                       ).pack(fill="x", pady=(0, 16))

    # --- Testen ---
    karte = ctk.CTkFrame(rahmen, fg_color=_KARTE, corner_radius=12, border_width=1, border_color=_LINIE)
    karte.pack(fill="x")
    innen = ctk.CTkFrame(karte, fg_color="transparent")
    innen.pack(fill="x", padx=20, pady=18)
    ctk.CTkLabel(innen, text=t("person.locked_try_title"), font=_schrift(15, True), anchor="w"
                 ).pack(fill="x")
    ctk.CTkLabel(innen, text=t("person.locked_try_text"), font=_schrift(13), text_color=_GRAU,
                 justify="left", anchor="w", wraplength=600).pack(fill="x", pady=(4, 14))
    _knopf(innen, t("person.request_trial"), lambda: webbrowser.open(anfrage_link())
           ).pack(anchor="w")

    # --- Code einloesen ---
    karte2 = ctk.CTkFrame(rahmen, fg_color=_KARTE, corner_radius=12, border_width=1, border_color=_LINIE)
    karte2.pack(fill="x", pady=(12, 0))
    innen2 = ctk.CTkFrame(karte2, fg_color="transparent")
    innen2.pack(fill="x", padx=20, pady=18)
    ctk.CTkLabel(innen2, text=t("person.code_label"), font=_schrift(15, True), anchor="w"
                 ).pack(fill="x")
    ctk.CTkLabel(innen2, text=t("person.code_hint"), font=_schrift(12), text_color=_GRAU, anchor="w"
                 ).pack(fill="x", pady=(2, 8))
    feld = ctk.CTkTextbox(innen2, height=64, font=(_MONO, 12), wrap="char", border_width=1,
                          border_color=_RAND, fg_color=_FELD, corner_radius=8)
    feld.pack(fill="x")
    meldung = ctk.CTkLabel(innen2, text="", font=_schrift(12), justify="left", anchor="w",
                           wraplength=600, text_color=_FEHLER)

    leiste = ctk.CTkFrame(innen2, fg_color="transparent")
    leiste.pack(fill="x", pady=(12, 0))

    def freischalten():
        ergebnis = lizenz.code_installieren(feld.get("1.0", "end"))
        if ergebnis.lizenziert:
            rahmen.destroy()
            if hasattr(app, "lizenz_hinweis_aktualisieren"):
                app.lizenz_hinweis_aktualisieren()
            _freigeschaltet(app, top, lizenz.status())
            return
        if ergebnis.art == "abgelaufen":
            meldung.configure(text=t("person.code_expired", bis=_datum(ergebnis.gueltig_bis)))
        else:
            meldung.configure(text=t("person.code_invalid"))
        feld.configure(border_color=_FEHLER)
        meldung.pack(fill="x", pady=(8, 0), before=leiste)

    knopf_frei = _knopf(leiste, t("person.activate"), freischalten, art="neben", width=120)
    knopf_frei.pack(side="left")

    # Sobald ein Code im Feld steht, ist "Freischalten" der naechste Schritt.
    def code_geaendert(_e=None):
        da = bool(feld.get("1.0", "end").strip())
        _knopf_art(knopf_frei, "primaer" if da else "neben")
        feld.configure(border_color=_RAND)
        meldung.pack_forget()
    feld.bind("<KeyRelease>", code_geaendert)
    feld.bind("<<Paste>>", lambda e: feld.after(10, code_geaendert))

    def lizenz_laden():
        top.destroy()
        app.oeffne_einstellungen_fenster()
        tabs = getattr(app, "einstellungen_tabs", None)
        if tabs is not None:
            try:
                tabs.set(t("settings.tab_license"))
            except Exception:
                pass

    _knopf(leiste, t("person.locked_settings"), lizenz_laden, art="text").pack(side="left", padx=(12, 0))

    _knopf(rahmen, t("person.close_button"), top.destroy, art="neben", width=110
           ).pack(side="bottom", anchor="e")


def _hinweisleiste(eltern, text):
    """Ruhige, getoente Leiste fuer Hinweise (kein Fehler)."""
    leiste = ctk.CTkFrame(eltern, fg_color=_HINWEIS_GRUND, corner_radius=8)
    leiste.text = ctk.CTkLabel(leiste, text=text, font=_schrift(12), text_color=_HINWEIS_TEXT,
                               justify="left", anchor="w", wraplength=640)
    leiste.text.pack(fill="x", padx=14, pady=9)
    return leiste


class _Personensuche:
    def __init__(self, app, top, lizenznehmer, hinweis="", test_bis=None):
        self.app = app
        self.top = top
        self.lizenznehmer = lizenznehmer
        self.ergebnis = None
        self.abbrechen = False
        self.laeuft = False

        rand = 28

        # --- Kopf ---
        kopf = ctk.CTkFrame(top, fg_color="transparent")
        kopf.pack(fill="x", padx=rand, pady=(24, 0))
        kopf.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(kopf, text=t("person.heading"), font=_schrift(20, True), anchor="w"
                     ).grid(row=0, column=0, sticky="w")
        if hinweis:
            tage = (test_bis - datetime.date.today()).days if test_bis else None
            text = (t("person.trial_badge_last") if tage == 0 else
                    t("person.trial_badge", tage=tage) if tage is not None else hinweis)
            marke = ctk.CTkLabel(kopf, text=text, font=_schrift(11, True), text_color=_HINWEIS_TEXT,
                                 fg_color=_HINWEIS_GRUND, corner_radius=10, height=22, padx=10)
            marke.grid(row=0, column=1, sticky="e", padx=(12, 0))
        ctk.CTkLabel(kopf, text=t("person.lead"), font=_schrift(13), text_color=_GRAU,
                     justify="left", anchor="w", wraplength=680
                     ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # --- Formular ---
        form = ctk.CTkFrame(top, fg_color=_KARTE, corner_radius=12, border_width=1, border_color=_LINIE)
        form.pack(fill="x", padx=rand, pady=(18, 0))
        raster = ctk.CTkFrame(form, fg_color="transparent")
        raster.pack(fill="x", padx=20, pady=(16, 16))
        # Sechs gleiche Spalten: Name 4 + Geburtsdatum 2, dann Anschrift,
        # E-Mail, Telefon zu je 2. So bleibt das Formular niedrig und die
        # Treffer bekommen den Platz.
        raster.grid_columnconfigure(tuple(range(6)), weight=1, uniform="spalte")

        self._fehlertexte = {}

        def zelle(zeile, spalte, breite, text, pflicht=False, nebentext=""):
            rahmen = ctk.CTkFrame(raster, fg_color="transparent")
            rahmen.grid(row=zeile, column=spalte, columnspan=breite, sticky="nsew",
                        padx=(0 if spalte == 0 else 6, 0 if spalte + breite == 6 else 6), pady=(0, 12))
            kopf = ctk.CTkFrame(rahmen, fg_color="transparent")
            kopf.pack(fill="x")
            ctk.CTkLabel(kopf, text=text.rstrip(" *"), font=_schrift(12, True), anchor="w",
                         height=18).pack(side="left")
            if pflicht or nebentext:
                ctk.CTkLabel(kopf, text=t("person.required") if pflicht else nebentext, font=_schrift(11),
                             text_color=_GRAU, height=18).pack(side="left", padx=(6, 0))
            fehler = ctk.CTkLabel(kopf, text="", font=_schrift(11), text_color=_FEHLER, height=18)
            fehler.pack(side="right")
            return rahmen, fehler

        def feld(zeile, spalte, breite, text, hinweis="", pflicht=False):
            rahmen, fehler = zelle(zeile, spalte, breite, text, pflicht)
            eingabe = ctk.CTkEntry(rahmen, placeholder_text=hinweis, height=34, font=_schrift(13),
                                   corner_radius=8, border_width=1, fg_color=_FELD, border_color=_RAND)
            eingabe.pack(fill="x", pady=(4, 0))
            eingabe.bind("<Return>", lambda e: self.suchen())
            eingabe.bind("<Key>", lambda e: self._feldfehler(eingabe, None), add="+")
            self._fehlertexte[eingabe] = fehler
            return eingabe

        self.f_name = feld(0, 0, 4, t("person.field_name"), t("person.field_name_hint"), pflicht=True)
        self.f_geburt = feld(0, 4, 2, t("person.field_birth"), t("person.field_birth_hint"))
        self.f_anschrift = feld(1, 0, 2, t("person.field_address"), t("person.field_address_hint"))
        self.f_email = feld(1, 2, 2, t("person.field_email"))
        self.f_telefon = feld(1, 4, 2, t("person.field_phone"))

        weitere, _ = zelle(2, 0, 4, t("person.field_more"), nebentext=t("person.field_more_hint"))
        weitere.grid_configure(pady=0)
        self.f_weitere = ctk.CTkTextbox(weitere, height=52, font=_schrift(13), border_width=1,
                                        border_color=_RAND, fg_color=_FELD, corner_radius=8)
        self.f_weitere.pack(fill="x", pady=(4, 0))

        self.knopf_suchen = _knopf(raster, t("person.search_button"), self.suchen, height=34)
        self.knopf_suchen.grid(row=2, column=4, columnspan=2, sticky="sew", padx=(6, 0))

        # --- Ergebnis ---
        self.ergebnis_kopf = ctk.CTkFrame(top, fg_color="transparent")
        self.ergebnis_kopf.grid_columnconfigure(1, weight=1)

        self.hinweise = ctk.CTkFrame(top, fg_color="transparent")

        self.flaeche = ctk.CTkFrame(top, fg_color="transparent")
        self.flaeche.pack(fill="both", expand=True, padx=rand, pady=(16, 0))
        self.liste = ctk.CTkScrollableFrame(self.flaeche, fg_color="transparent", corner_radius=0)
        self.zustand = ctk.CTkFrame(self.flaeche, fg_color="transparent", corner_radius=12,
                                    border_width=1, border_color=_LINIE)

        # --- Fuss ---
        unten = ctk.CTkFrame(top, fg_color="transparent")
        unten.pack(fill="x", padx=rand, pady=(12, 20), before=self.flaeche, side="bottom")
        self.status = ctk.CTkLabel(unten, text="", font=_schrift(12), text_color=_GRAU,
                                   justify="left", anchor="w", wraplength=380)
        self.status.pack(side="left", fill="x", expand=True)
        self.knopf_bericht = _knopf(unten, t("person.report_button"), self.bericht_speichern,
                                    art="neben", state="disabled")
        self.knopf_bericht.pack(side="right")
        _knopf(unten, t("person.close_button"), self.schliessen, art="neben", width=110
               ).pack(side="right", padx=(0, 10))
        top.protocol("WM_DELETE_WINDOW", self.schliessen)

        self._zeige_zustand(t("person.empty_title"), t("person.empty_text"))
        self.f_name.focus_set()

    # ---------- Anzeige ----------

    def _feldfehler(self, eingabe, text):
        self._fehlertexte[eingabe].configure(text=text or "")
        eingabe.configure(border_color=_FEHLER if text else _RAND)

    def _leeren(self):
        for w in self.zustand.winfo_children():
            w.destroy()
        for w in self.liste.winfo_children():
            w.destroy()
        for w in self.ergebnis_kopf.winfo_children():
            w.destroy()
        for w in self.hinweise.winfo_children():
            w.destroy()
        self.zustand.pack_forget()
        self.liste.pack_forget()
        self.ergebnis_kopf.pack_forget()
        self.hinweise.pack_forget()

    def _zeige_zustand(self, titel, text="", farbe=None, fortschritt=False):
        """Ruhige Ansicht in der Mitte der Trefferflaeche."""
        self._leeren()
        self.zustand.pack(fill="both", expand=True)
        mitte = ctk.CTkFrame(self.zustand, fg_color="transparent")
        mitte.place(relx=0.5, rely=0.45, anchor="center")
        self.zustand_titel = ctk.CTkLabel(mitte, text=titel, font=_schrift(15, True),
                                          text_color=farbe or _TEXT)
        self.zustand_titel.pack()
        self.zustand_text = ctk.CTkLabel(mitte, text=text, font=_schrift(13), text_color=_GRAU,
                                         justify="center", wraplength=440)
        if text:
            self.zustand_text.pack(pady=(4, 0))
        if fortschritt:
            self.fortschritt = ctk.CTkProgressBar(mitte, width=280, height=6, corner_radius=3,
                                                  mode="indeterminate")
            self.fortschritt.pack(pady=(14, 0))
            self.fortschritt.start()

    def _fortschritt_melden(self, n, gesamt):
        if not self.laeuft or not self.top.winfo_exists():
            return
        self.zustand_text.configure(text=t("person.searching", n=_zahl(n), gesamt=_zahl(gesamt)))
        if not self.zustand_text.winfo_ismapped():
            self.zustand_text.pack(pady=(4, 0), before=self.fortschritt)
        if gesamt and str(self.fortschritt.cget("mode")) != "determinate":
            self.fortschritt.stop()
            self.fortschritt.configure(mode="determinate")
        if gesamt:
            self.fortschritt.set(n / gesamt)

    def _hinweis(self, texte):
        for text in texte:
            _hinweisleiste(self.hinweise, text).pack(fill="x", pady=(0, 6))
        if texte:
            self.hinweise.pack(fill="x", padx=28, pady=(14, 0), before=self.flaeche)

    # ---------- Ablauf ----------

    def person(self):
        weitere = [z.strip() for z in self.f_weitere.get("1.0", "end").splitlines() if z.strip()]
        return ps.Person(
            name=self.f_name.get(), geburtsdatum=self.f_geburt.get(),
            anschrift=self.f_anschrift.get(), email=self.f_email.get(),
            telefon=self.f_telefon.get(), weitere=weitere)

    def suchen(self):
        if self.laeuft:
            self.abbrechen = True
            return
        person = self.person()
        self._feldfehler(self.f_name, None)
        self._feldfehler(self.f_geburt, None)
        try:
            ps.suchplan(person)          # Eingaben pruefen, bevor der Index geladen wird
        except ps.EingabeFehler as e:
            if e.args[0] == "geburtsdatum_unlesbar":
                self._feldfehler(self.f_geburt, t("person.field_birth_hint"))
                self.status.configure(text=t("person.error_birth"), text_color=_FEHLER)
                self.f_geburt.focus_set()
            else:
                self._feldfehler(self.f_name, t("person.error_name"))
                self.f_name.focus_set()
            return

        self.laeuft = True
        self.abbrechen = False
        self.ergebnis = None
        self.knopf_bericht.configure(state="disabled")
        _knopf_art(self.knopf_bericht, "neben")
        _knopf_art(self.knopf_suchen, "neben")
        self.knopf_suchen.configure(text=t("person.cancel_button"))
        self.status.configure(text="", text_color=_GRAU)
        self._zeige_zustand(t("person.running_title"), fortschritt=True)
        if getattr(self.app, "indexierung_laeuft", False):
            self._hinweis([t("person.indexing_warning")])

        def melden(n, gesamt):
            self.top.after(0, lambda: self._fortschritt_melden(n, gesamt))

        def arbeit():
            try:
                ergebnis = ps.durchsuchen(person, soll_abbrechen=lambda: self.abbrechen, melden=melden)
                self.top.after(0, lambda: self.fertig(ergebnis))
            except Exception as e:
                fehler = str(e)
                self.top.after(0, lambda: self.fehlgeschlagen(fehler))

        threading.Thread(target=arbeit, daemon=True).start()

    def _suche_beendet(self):
        self.laeuft = False
        self.knopf_suchen.configure(text=t("person.search_button"))
        _knopf_art(self.knopf_suchen, "primaer")

    def fehlgeschlagen(self, fehler):
        if not self.top.winfo_exists():
            return
        self._suche_beendet()
        self._zeige_zustand(t("person.error_title"), fehler, farbe=_FEHLER)

    def fertig(self, ergebnis):
        if not self.top.winfo_exists():
            return
        self._suche_beendet()
        self.ergebnis = ergebnis

        if ergebnis.dateien_durchsucht == 0 and not ergebnis.nicht_lesbar:
            self._zeige_zustand(t("person.no_index_title"), t("person.no_index"), farbe=_FEHLER)
            return

        if ergebnis.funde:
            self._leeren()
            self._ergebnis_kopf(ergebnis)
            self.liste.pack(fill="both", expand=True)
            self._liste_fuellen(ergebnis)
        else:
            self._zeige_zustand(t("person.no_results_title"), t(
                "person.no_results_text", durchsucht=_zahl(ergebnis.dateien_durchsucht)))

        hinweise = []
        if ergebnis.abgebrochen:
            hinweise.append(t("person.cancelled"))
        if ergebnis.nicht_lesbar:
            hinweise.append(t("person.unreadable_warning", anzahl=_zahl(len(ergebnis.nicht_lesbar))))
        if getattr(self.app, "indexierung_laeuft", False):
            hinweise.append(t("person.indexing_warning"))
        self._hinweis(hinweise)

        # Der Bericht ist jetzt der naechste Schritt - auch ohne Funde,
        # denn "nichts gefunden" ist ebenfalls ein Nachweis fuer die Akte.
        self.knopf_bericht.configure(state="normal")
        _knopf_art(self.knopf_bericht, "primaer")
        _knopf_art(self.knopf_suchen, "neben")

    def _ergebnis_kopf(self, ergebnis):
        k = self.ergebnis_kopf
        k.pack(fill="x", padx=28, pady=(22, 0), before=self.flaeche)
        ctk.CTkLabel(k, text=t("person.results_title"), font=_schrift(15, True), anchor="w"
                     ).grid(row=0, column=0, sticky="w")
        zaehler = ctk.CTkFrame(k, fg_color="transparent")
        zaehler.grid(row=0, column=1, sticky="w", padx=(16, 0))
        for stufe in ps.STUFEN:
            n = ergebnis.anzahl(stufe)
            if not n:
                continue
            _punkt(zaehler, _STUFENFARBE[stufe]).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(zaehler, text=f"{_zahl(n)} {t(f'person.level_{stufe}')}", font=_schrift(13),
                         height=20).pack(side="left", padx=(0, 16))
        ctk.CTkLabel(k, text=t("person.files_searched", anzahl=_zahl(ergebnis.dateien_durchsucht)),
                     font=_schrift(12), text_color=_GRAU).grid(row=0, column=2, sticky="e")

    def _liste_fuellen(self, ergebnis):
        namen = merkmal_namen()
        letzte_stufe = None
        for f in ergebnis.funde[:MAX_ZEILEN]:
            if f.stufe != letzte_stufe:
                letzte_stufe = f.stufe
                kopf = ctk.CTkFrame(self.liste, fg_color="transparent")
                kopf.pack(fill="x", pady=(14 if letzte_stufe != ergebnis.funde[0].stufe else 2, 6))
                _punkt(kopf, _STUFENFARBE[f.stufe]).pack(side="left", padx=(2, 8))
                ctk.CTkLabel(kopf, text=t(f"person.level_{f.stufe}"), font=_schrift(13, True), height=20
                             ).pack(side="left")
                ctk.CTkLabel(kopf, text=_zahl(ergebnis.anzahl(f.stufe)), font=_schrift(13),
                             text_color=_GRAU, height=20).pack(side="left", padx=(6, 0))
                ctk.CTkLabel(kopf, text=t(f"person.level_{f.stufe}_explain"), font=_schrift(12),
                             text_color=_GRAU, height=20, anchor="w").pack(side="left", padx=(12, 0))
            self._zeile(f, namen)
        rest = len(ergebnis.funde) - MAX_ZEILEN
        if rest > 0:
            ctk.CTkLabel(self.liste, text=t("person.more_rows", anzahl=_zahl(rest)), font=_schrift(12),
                         text_color=_GRAU).pack(pady=(10, 4))

    def _zeile(self, fund, namen):
        rahmen = ctk.CTkFrame(self.liste, fg_color=_KARTE, corner_radius=10, border_width=1,
                              border_color=_LINIE)
        rahmen.pack(fill="x", pady=(0, 6), padx=(0, 6))
        rahmen.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(rahmen, text=os.path.basename(fund.datei), font=_schrift(13, True),
                     anchor="w", height=20).grid(row=0, column=0, padx=(16, 8), pady=(12, 0), sticky="w")
        ctk.CTkLabel(rahmen, text=_kurzpfad(os.path.dirname(fund.datei)), font=_schrift(11),
                     text_color=_GRAU, anchor="w", height=16
                     ).grid(row=1, column=0, padx=(16, 8), pady=(1, 0), sticky="w")

        if fund.stellen:
            s = fund.stellen[0]
            marker, marker_text = _MARKER["Dark" if ctk.get_appearance_mode() == "Dark" else "Light"]
            text = ctk.CTkTextbox(rahmen, height=20, font=_schrift(12), wrap="word", fg_color=_KARTE,
                                  border_width=0, corner_radius=0, activate_scrollbars=False,
                                  text_color=_TEXT)
            text._textbox.configure(padx=0, pady=0, spacing1=1, spacing3=1, cursor="arrow")
            text.insert("end", s.vor)
            text.insert("end", s.treffer, "treffer")
            text.insert("end", s.nach)
            text.tag_config("treffer", background=marker, foreground=marker_text)
            text.configure(state="disabled")
            text.grid(row=2, column=0, padx=(16 - 3, 8), pady=(8, 0), sticky="ew")

            # Hoehe nach der tatsaechlichen Zeilenzahl beim Umbrechen. Nur
            # aendern, wenn sie sich aendert - sonst loest jede neue Hoehe
            # das naechste <Configure> aus.
            def hoehe_anpassen(_e=None, w=text):
                zeilen = w._textbox.count("1.0", "end", "displaylines")
                if isinstance(zeilen, tuple):
                    zeilen = zeilen[0]
                hoehe = max(1, zeilen or 1) * 18 + 2
                if w.cget("height") != hoehe:
                    w.configure(height=hoehe)
            text._textbox.bind("<Configure>", hoehe_anpassen, add="+")

        merkmale = ctk.CTkFrame(rahmen, fg_color="transparent")
        merkmale.grid(row=3, column=0, padx=(16, 8), pady=(8, 12), sticky="w")
        for m in ps.merkmale_zum_zeigen(fund.merkmale):
            ctk.CTkLabel(merkmale, text=namen[m], font=_schrift(11), text_color=_GRAU,
                         fg_color=farben.FLAECHE, corner_radius=8, height=20, padx=8
                         ).pack(side="left", padx=(0, 6))

        knoepfe = ctk.CTkFrame(rahmen, fg_color="transparent")
        knoepfe.grid(row=0, column=1, rowspan=2, padx=(0, 12), pady=(12, 0), sticky="ne")
        _knopf(knoepfe, t("person.show_button"), lambda p=fund.datei: plattform.im_dateimanager_zeigen(p),
               art="text", height=28, font=_schrift(12)).pack(side="left", padx=(0, 4))
        _knopf(knoepfe, t("person.open_button"), lambda p=fund.datei: plattform.datei_oeffnen(p),
               art="neben", height=28, width=72, font=_schrift(12)).pack(side="left")

    def bericht_speichern(self):
        if self.ergebnis is None:
            return
        pfad = filedialog.asksaveasfilename(
            parent=self.top, title=t("person.report_button"), defaultextension=".pdf",
            initialfile=dateiname_fuer_bericht(self.ergebnis.person),
            filetypes=[("PDF", "*.pdf")])
        if not pfad:
            return
        try:
            bericht.schreiben(pfad, self.ergebnis, bericht_texte(), merkmal_namen(),
                              version.APP_VERSION, self.lizenznehmer)
        except Exception as e:
            self.status.configure(text=t("person.report_failed", fehler=e), text_color=_FEHLER)
            return
        self.status.configure(text=t("person.report_saved", pfad=_kurzpfad(pfad)), text_color=_ERFOLG)
        plattform.datei_oeffnen(pfad)

    def schliessen(self):
        self.abbrechen = True
        self.top.destroy()
