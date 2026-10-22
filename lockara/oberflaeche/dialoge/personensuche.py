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
"""

import datetime
import os
import re
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
from lockara.oberflaeche.i18n import t

# So viele Dateien zeigt die Liste; der Bericht enthaelt immer alle.
# CustomTkinter wird bei einigen hundert Zeilen spuerbar langsam.
MAX_ZEILEN = 200

_STUFENFARBE = {ps.SICHER: "#2e7d32", ps.WAHRSCHEINLICH: "#ef6c00", ps.PRUEFEN: "#78909c"}
_GRAU = "#78909c"


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
    top.geometry("760x720")
    top.minsize(620, 520)
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
    _Personensuche(app, top, name, hinweis)


def anfrage_link():
    """mailto-Link fuer die Anfrage einer Testlizenz."""
    return (f"mailto:{RUECKMELDUNG_ADRESSE}"
            f"?subject={urllib.parse.quote(t('person.mail_subject'))}"
            f"&body={urllib.parse.quote(t('person.mail_body'))}")


def _gesperrt(app, top, stand):
    """Ohne Lizenz: wofuer die Funktion da ist, wie man sie testet, und ein
    Feld fuer den Lizenzcode aus der E-Mail."""
    rahmen = ctk.CTkFrame(top, fg_color="transparent")
    rahmen.pack(fill="both", expand=True)

    ctk.CTkLabel(rahmen, text=t("person.locked_heading"), font=("Helvetica", 16, "bold")
                 ).pack(padx=24, pady=(28, 8), anchor="w")
    ctk.CTkLabel(rahmen, text=t("person.locked_text"), font=("Helvetica", 12), justify="left",
                 wraplength=680, text_color=_GRAU).pack(padx=24, pady=(0, 14), anchor="w")
    if stand.ist_test and stand.art == "abgelaufen":
        ctk.CTkLabel(rahmen, text=t("person.trial_expired", bis=_datum(stand.gueltig_bis)),
                     font=("Helvetica", 12), justify="left", wraplength=680,
                     text_color="#ef6c00").pack(padx=24, pady=(0, 14), anchor="w")

    ctk.CTkButton(rahmen, text=t("person.request_trial"),
                  command=lambda: webbrowser.open(anfrage_link())).pack(padx=24, pady=(0, 22), anchor="w")

    ctk.CTkLabel(rahmen, text=t("person.code_label"), font=("Helvetica", 12, "bold")
                 ).pack(padx=24, pady=(0, 2), anchor="w")
    ctk.CTkLabel(rahmen, text=t("person.code_hint"), font=("Helvetica", 10),
                 text_color=_GRAU).pack(padx=24, anchor="w")
    feld = ctk.CTkTextbox(rahmen, height=90)
    feld.pack(padx=24, pady=(4, 6), fill="x")
    meldung = ctk.CTkLabel(rahmen, text="", font=("Helvetica", 11), justify="left",
                           wraplength=680, text_color="#c62828")

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

    leiste = ctk.CTkFrame(rahmen, fg_color="transparent")
    leiste.pack(fill="x", padx=24, pady=(0, 4))
    ctk.CTkButton(leiste, text=t("person.activate"), command=freischalten).pack(side="left")

    def lizenz_laden():
        top.destroy()
        app.oeffne_einstellungen_fenster()
        tabs = getattr(app, "einstellungen_tabs", None)
        if tabs is not None:
            try:
                tabs.set(t("settings.tab_license"))
            except Exception:
                pass

    ctk.CTkButton(leiste, text=t("person.locked_settings"), fg_color=farben.SEITE_KNOPF,
                  hover_color=farben.SEITE_KNOPF_HOVER, command=lizenz_laden).pack(side="left", padx=10)
    meldung.pack(padx=24, pady=(4, 0), anchor="w")

    ctk.CTkButton(rahmen, text=t("person.close_button"), fg_color=farben.SEITE_KNOPF,
                  hover_color=farben.SEITE_KNOPF_HOVER, command=top.destroy
                  ).pack(side="bottom", anchor="e", padx=24, pady=(0, 20))


class _Personensuche:
    def __init__(self, app, top, lizenznehmer, hinweis=""):
        self.app = app
        self.top = top
        self.lizenznehmer = lizenznehmer
        self.ergebnis = None
        self.abbrechen = False
        self.laeuft = False

        ctk.CTkLabel(top, text=t("person.heading"), font=("Helvetica", 16, "bold")
                     ).pack(padx=20, pady=(18, 2), anchor="w")
        ctk.CTkLabel(top, text=t("person.intro"), font=("Helvetica", 11), justify="left",
                     wraplength=700, text_color=_GRAU).pack(padx=20, pady=(0, 10), anchor="w")
        if hinweis:
            ctk.CTkLabel(top, text=hinweis, font=("Helvetica", 11, "bold"),
                         text_color="#ef6c00").pack(padx=20, pady=(0, 8), anchor="w")

        # --- Formular ---
        form = ctk.CTkFrame(top, corner_radius=10)
        form.pack(fill="x", padx=20, pady=(0, 8))
        form.grid_columnconfigure(1, weight=1)
        form.grid_columnconfigure(3, weight=1)

        def feld(zeile, spalte, text, hinweis=""):
            ctk.CTkLabel(form, text=text, font=("Helvetica", 11)).grid(
                row=zeile, column=spalte, padx=(12, 6), pady=5, sticky="w")
            eingabe = ctk.CTkEntry(form, placeholder_text=hinweis, height=30)
            eingabe.grid(row=zeile, column=spalte + 1, padx=(0, 12), pady=5, sticky="ew")
            eingabe.bind("<Return>", lambda e: self.suchen())
            return eingabe

        self.f_name = feld(0, 0, t("person.field_name"), t("person.field_name_hint"))
        self.f_geburt = feld(0, 2, t("person.field_birth"), t("person.field_birth_hint"))
        self.f_anschrift = feld(1, 0, t("person.field_address"), t("person.field_address_hint"))
        self.f_email = feld(1, 2, t("person.field_email"))
        self.f_telefon = feld(2, 0, t("person.field_phone"))

        ctk.CTkLabel(form, text=t("person.field_more"), font=("Helvetica", 11)).grid(
            row=3, column=0, padx=(12, 6), pady=(5, 10), sticky="nw")
        self.f_weitere = ctk.CTkTextbox(form, height=52)
        self.f_weitere.grid(row=3, column=1, columnspan=3, padx=(0, 12), pady=(5, 2), sticky="ew")
        ctk.CTkLabel(form, text=t("person.field_more_hint"), font=("Helvetica", 10),
                     text_color=_GRAU).grid(row=4, column=1, columnspan=3, padx=(0, 12),
                                            pady=(0, 8), sticky="w")

        # --- Suchen ---
        zeile = ctk.CTkFrame(top, fg_color="transparent")
        zeile.pack(fill="x", padx=20, pady=(2, 4))
        self.knopf_suchen = ctk.CTkButton(zeile, text=t("person.search_button"), width=120,
                                          command=self.suchen)
        self.knopf_suchen.pack(side="left")
        self.status = ctk.CTkLabel(zeile, text="", font=("Helvetica", 11), justify="left",
                                   wraplength=560, text_color=_GRAU)
        self.status.pack(side="left", padx=12)

        self.warnung = ctk.CTkLabel(top, text="", font=("Helvetica", 11), justify="left",
                                    wraplength=700, text_color="#ef6c00")
        self.warnung.pack(padx=20, anchor="w")

        # --- Treffer ---
        self.liste = ctk.CTkScrollableFrame(top, corner_radius=10)
        self.liste.pack(fill="both", expand=True, padx=20, pady=(4, 8))

        unten = ctk.CTkFrame(top, fg_color="transparent")
        unten.pack(fill="x", padx=20, pady=(0, 16))
        self.knopf_bericht = ctk.CTkButton(unten, text=t("person.report_button"),
                                           state="disabled", command=self.bericht_speichern)
        self.knopf_bericht.pack(side="left")
        ctk.CTkButton(unten, text=t("person.close_button"), fg_color=farben.SEITE_KNOPF,
                      hover_color=farben.SEITE_KNOPF_HOVER, command=self.schliessen
                      ).pack(side="right")
        top.protocol("WM_DELETE_WINDOW", self.schliessen)

        self.f_name.focus_set()

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
        try:
            ps.suchplan(person)          # Eingaben pruefen, bevor der Index geladen wird
        except ps.EingabeFehler as e:
            self.status.configure(text=t("person.error_birth") if e.args[0] == "geburtsdatum_unlesbar"
                                  else t("person.error_name"), text_color="#c62828")
            return

        self.laeuft = True
        self.abbrechen = False
        self.ergebnis = None
        self.knopf_bericht.configure(state="disabled")
        self.knopf_suchen.configure(text=t("person.cancel_button"))
        self.status.configure(text="", text_color=_GRAU)
        self.warnung.configure(
            text=t("person.indexing_warning") if getattr(self.app, "indexierung_laeuft", False) else "")
        for w in self.liste.winfo_children():
            w.destroy()

        def melden(n, gesamt):
            self.top.after(0, lambda: self.status.configure(text=t("person.searching", n=n, gesamt=gesamt)))

        def arbeit():
            try:
                ergebnis = ps.durchsuchen(person, soll_abbrechen=lambda: self.abbrechen, melden=melden)
                self.top.after(0, lambda: self.fertig(ergebnis))
            except Exception as e:
                fehler = str(e)
                self.top.after(0, lambda: self.fehlgeschlagen(fehler))

        threading.Thread(target=arbeit, daemon=True).start()

    def fehlgeschlagen(self, fehler):
        if not self.top.winfo_exists():
            return
        self.laeuft = False
        self.knopf_suchen.configure(text=t("person.search_button"))
        self.status.configure(text=t("person.error_general", fehler=fehler), text_color="#c62828")

    def fertig(self, ergebnis):
        if not self.top.winfo_exists():
            return
        self.laeuft = False
        self.ergebnis = ergebnis
        self.knopf_suchen.configure(text=t("person.search_button"))

        if ergebnis.dateien_durchsucht == 0 and not ergebnis.nicht_lesbar:
            self.status.configure(text=t("person.no_index"), text_color="#c62828")
            return

        if ergebnis.funde:
            self.status.configure(text=t(
                "person.summary", gesamt=len(ergebnis.funde), sicher=ergebnis.anzahl(ps.SICHER),
                wahrscheinlich=ergebnis.anzahl(ps.WAHRSCHEINLICH), pruefen=ergebnis.anzahl(ps.PRUEFEN),
                durchsucht=ergebnis.dateien_durchsucht), text_color=_GRAU)
        else:
            self.status.configure(text=t("person.no_results", durchsucht=ergebnis.dateien_durchsucht))

        hinweise = []
        if ergebnis.abgebrochen:
            hinweise.append(t("person.cancelled"))
        if ergebnis.nicht_lesbar:
            hinweise.append(t("person.unreadable_warning", anzahl=len(ergebnis.nicht_lesbar)))
        if getattr(self.app, "indexierung_laeuft", False):
            hinweise.append(t("person.indexing_warning"))
        self.warnung.configure(text="\n".join(hinweise))

        self.knopf_bericht.configure(state="normal")
        self._liste_fuellen(ergebnis)

    def _liste_fuellen(self, ergebnis):
        namen = merkmal_namen()
        letzte_stufe = None
        for f in ergebnis.funde[:MAX_ZEILEN]:
            if f.stufe != letzte_stufe:
                letzte_stufe = f.stufe
                kopf = ctk.CTkFrame(self.liste, fg_color="transparent")
                kopf.pack(fill="x", pady=(10, 2))
                ctk.CTkLabel(kopf, text="●  " + t(f"person.level_{f.stufe}") +
                             f"  ({ergebnis.anzahl(f.stufe)})", font=("Helvetica", 12, "bold"),
                             text_color=_STUFENFARBE[f.stufe]).pack(side="left")
                ctk.CTkLabel(kopf, text=t(f"person.level_{f.stufe}_explain"), font=("Helvetica", 10),
                             text_color=_GRAU).pack(side="left", padx=10)
            self._zeile(f, namen)

    def _zeile(self, fund, namen):
        rahmen = ctk.CTkFrame(self.liste, corner_radius=8)
        rahmen.pack(fill="x", pady=3, padx=2)
        rahmen.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(rahmen, text=os.path.basename(fund.datei), font=("Helvetica", 12, "bold"),
                     anchor="w").grid(row=0, column=0, padx=10, pady=(6, 0), sticky="w")
        ctk.CTkLabel(rahmen, text=os.path.dirname(fund.datei) + "   ·   " +
                     ", ".join(namen[m] for m in ps.merkmale_zum_zeigen(fund.merkmale)), font=("Helvetica", 10),
                     text_color=_GRAU, anchor="w", justify="left", wraplength=520
                     ).grid(row=1, column=0, padx=10, sticky="w")
        if fund.stellen:
            s = fund.stellen[0]
            ctk.CTkLabel(rahmen, text=f"{s.vor}»{s.treffer}«{s.nach}", font=("Helvetica", 10),
                         anchor="w", justify="left", wraplength=520
                         ).grid(row=2, column=0, padx=10, pady=(2, 6), sticky="w")

        knoepfe = ctk.CTkFrame(rahmen, fg_color="transparent")
        knoepfe.grid(row=0, column=1, rowspan=3, padx=8, pady=6, sticky="e")
        ctk.CTkButton(knoepfe, text=t("person.open_button"), width=70, height=26,
                      command=lambda p=fund.datei: plattform.datei_oeffnen(p)).pack(pady=2)
        ctk.CTkButton(knoepfe, text=t("person.show_button"), width=70, height=26,
                      fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER,
                      command=lambda p=fund.datei: plattform.im_dateimanager_zeigen(p)).pack(pady=2)

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
            self.status.configure(text=t("person.report_failed", fehler=e), text_color="#c62828")
            return
        self.status.configure(text=t("person.report_saved", pfad=pfad), text_color="#2e7d32")
        plattform.datei_oeffnen(pfad)

    def schliessen(self):
        self.abbrechen = True
        self.top.destroy()
