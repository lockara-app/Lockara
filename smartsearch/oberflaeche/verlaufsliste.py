#!/usr/bin/env python3
"""
verlaufsliste.py - die letzten Suchanfragen als Liste unter dem Suchfeld.

WARUM ES DAS GIBT
-----------------
Der Suchverlauf wurde seit jeher in verlauf.json gespeichert
(kern/einstellungen.py), aber nirgends mehr angezeigt. Wer dieselbe Akte
oder Rechnung jede Woche sucht, tippt so jedes Mal dieselbe Anfrage neu.

WIE ES SICH VERHAELT
--------------------
- Klick ins leere Suchfeld (oder Pfeil nach unten): die letzten Anfragen
  erscheinen unter dem Feld.
- Beim Tippen bleiben nur Anfragen stehen, die das Getippte enthalten.
  Passt keine, verschwindet die Liste - sie soll nie im Weg sein.
- Pfeiltasten waehlen aus, Eingabe sucht, Escape schliesst nur die Liste
  (nicht das ganze Fenster). Klick auf einen Eintrag sucht sofort.
- Ganz unten "Suchverlauf löschen": In Kanzleien koennen schon Suchbegriffe
  vertraulich sein (Namen von Mandanten). Der Verlauf muss sich deshalb
  ohne Umweg ueber die Einstellungen loeschen lassen.

Die Liste liegt als eingeblendeter Rahmen ueber den Suchergebnissen
(place), nicht als eigenes Fenster. Ein zweites Fenster wuerde auf dem Mac
den Fokus stehlen - und SmartSearch versteckt sich, sobald es den Fokus
verliert (siehe Hauptfenster.auf_fokus_verlust).
"""

import customtkinter as ctk

from smartsearch.oberflaeche import farben
from smartsearch.oberflaeche.i18n import t

# So viele Eintraege zeigt die Liste hoechstens. Gespeichert werden mehr
# (MAX_VERLAUF in kern/einstellungen.py); wer weiter zurueck will, tippt
# den Anfang und bekommt die passenden.
SICHTBAR_MAX = 8

ZEILEN_HOEHE = 28


class Verlaufsliste:
    """Haengt sich an ein Suchfeld. Kennt den Verlauf nicht selbst, sondern
    fragt ihn ueber hole_verlauf() ab - so bleibt das Hauptfenster die
    einzige Stelle, die den Verlauf haelt und speichert.

    hole_verlauf()        -> Liste der Anfragen, neueste zuerst
    bei_auswahl(anfrage)  -> wird mit der gewaehlten Anfrage aufgerufen
    bei_loeschen()        -> Verlauf leeren (Hauptfenster speichert)
    """

    def __init__(self, eltern, suchfeld, hole_verlauf, bei_auswahl, bei_loeschen,
                 platzhalter=""):
        self.eltern = eltern
        self.suchfeld = suchfeld
        self.hole_verlauf = hole_verlauf
        self.bei_auswahl = bei_auswahl
        self.bei_loeschen = bei_loeschen
        self.platzhalter = platzhalter

        self.rahmen = None
        self.zeilen = []          # (Rahmen, Anfrage)
        self.markiert = -1
        self._eintraege = []
        self._schliessen_geplant = None

        suchfeld.bind("<FocusIn>", self._bei_fokus, add="+")
        suchfeld.bind("<FocusOut>", self._bei_fokusverlust, add="+")
        suchfeld.bind("<KeyRelease>", self._bei_taste, add="+")
        # Pfeiltasten, Eingabe und Escape gehoeren der Liste, solange sie
        # offen ist. "break" haelt sie davon ab, zusaetzlich die Bindungen
        # des Fensters auszuloesen (Trefferkarten wandern, Fenster
        # verschwindet).
        suchfeld.bind("<Down>", self._runter)
        suchfeld.bind("<Up>", self._hoch)
        suchfeld.bind("<Escape>", self._escape)

    # ---------- oeffentlich ----------

    def ist_offen(self):
        return self.rahmen is not None

    def eingabe_abfangen(self):
        """Fuer die Eingabetaste im Suchfeld. Ist ein Eintrag markiert, wird
        der gesucht und True zurueckgegeben - der Aufrufer sucht dann nicht
        noch einmal mit dem Feldinhalt."""
        if self.ist_offen() and 0 <= self.markiert < len(self._eintraege):
            self._waehlen(self._eintraege[self.markiert])
            return True
        self.schliessen()
        return False

    def schliessen(self):
        if self._schliessen_geplant is not None:
            try:
                self.eltern.after_cancel(self._schliessen_geplant)
            except Exception:
                pass
            self._schliessen_geplant = None
        if self.rahmen is not None:
            try:
                self.rahmen.destroy()
            except Exception:
                pass
        self.rahmen = None
        self.zeilen = []
        self.markiert = -1
        self._eintraege = []

    # ---------- Ereignisse ----------

    def _feldtext(self):
        text = self.suchfeld.get().strip()
        return "" if text == self.platzhalter else text

    def _bei_fokus(self, event=None):
        if not self._feldtext():
            self._oeffnen()

    def _bei_fokusverlust(self, event=None):
        # Verzoegert: ein Klick auf einen Eintrag nimmt dem Feld unter
        # Umstaenden kurz den Fokus. Ohne die Pause waere die Liste schon
        # weg, bevor der Klick ankommt.
        if self.ist_offen() and self._schliessen_geplant is None:
            self._schliessen_geplant = self.eltern.after(200, self._spaet_schliessen)

    def _spaet_schliessen(self):
        self._schliessen_geplant = None
        try:
            if self.eltern.focus_get() is self.suchfeld._entry:
                return
        except Exception:
            pass
        self.schliessen()

    def _bei_taste(self, event):
        if event.keysym in ("Down", "Up", "Return", "KP_Enter", "Escape",
                            "Left", "Right", "Shift_L", "Shift_R", "Meta_L",
                            "Meta_R", "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return
        self._oeffnen()

    def _runter(self, event=None):
        if not self.ist_offen():
            # Pfeil nach unten im Feld oeffnet die Liste - so kommt man
            # auch per Tastatur an den Verlauf.
            if self._oeffnen() and self.zeilen:
                self._markieren(0)
                return "break"
            return None   # weiter an die Trefferkarten (Fenster-Bindung)
        self._markieren(min(self.markiert + 1, len(self.zeilen) - 1))
        return "break"

    def _hoch(self, event=None):
        if not self.ist_offen():
            return None
        if self.markiert <= 0:
            self._markieren(-1)
        else:
            self._markieren(self.markiert - 1)
        return "break"

    def _escape(self, event=None):
        if self.ist_offen():
            self.schliessen()
            return "break"
        return None   # Fenster-Bindung: Fenster ausblenden

    # ---------- Aufbau ----------

    def _passende(self):
        text = self._feldtext().lower()
        verlauf = [v for v in (self.hole_verlauf() or []) if isinstance(v, str) and v.strip()]
        if text:
            # Genau das Getippte noch einmal anzubieten, hilft niemandem.
            verlauf = [v for v in verlauf if text in v.lower() and v.lower() != text]
        return verlauf[:SICHTBAR_MAX]

    def _oeffnen(self):
        """Zeigt die passenden Eintraege. False, wenn es keine gibt."""
        eintraege = self._passende()
        if eintraege == self._eintraege and self.ist_offen():
            return True
        self.schliessen()
        if not eintraege:
            return False
        self._eintraege = eintraege

        # Der Rahmen haengt am selben Eltern-Rahmen wie das Suchfeld-Panel
        # und wird direkt darunter eingeblendet, in voller Breite.
        panel = self.suchfeld.master
        traeger = panel.master
        traeger.update_idletasks()
        y = panel.winfo_y() + panel.winfo_height() + 2

        self.rahmen = ctk.CTkFrame(
            traeger, corner_radius=8, fg_color=farben.FELD,
            border_width=1, border_color=farben.LINIE)

        kopf = ctk.CTkLabel(
            self.rahmen, text=t("history.title"), anchor="w",
            font=("Helvetica", 10), text_color=farben.GEDAEMPFT)
        kopf.pack(fill="x", padx=12, pady=(6, 0))

        for i, anfrage in enumerate(eintraege):
            zeile = ctk.CTkFrame(self.rahmen, corner_radius=6, height=ZEILEN_HOEHE,
                                 fg_color="transparent")
            zeile.pack(fill="x", padx=4, pady=0)
            zeile.pack_propagate(False)
            beschriftung = ctk.CTkLabel(
                zeile, text=anfrage, anchor="w", font=("Helvetica", 12),
                text_color=farben.TEXT)
            beschriftung.pack(fill="both", expand=True, padx=8)
            for w in (zeile, beschriftung):
                w.bind("<Button-1>", lambda e, a=anfrage: self._waehlen(a))
                w.bind("<Enter>", lambda e, n=i: self._markieren(n))
                try:
                    w.configure(cursor="hand2")
                except Exception:
                    pass
            self.zeilen.append((zeile, anfrage))

        loeschen = ctk.CTkButton(
            self.rahmen, text=t("history.clear"), height=22, width=10,
            font=("Helvetica", 10), fg_color="transparent",
            hover_color=farben.MARKIERT, text_color=farben.GEDAEMPFT,
            anchor="e", command=self._loeschen)
        loeschen.pack(anchor="e", padx=6, pady=(2, 6))

        # relwidth statt einer festen Breite: das Suchfeld-Panel fuellt den
        # Hauptbereich ganz aus, und so waechst die Liste mit, wenn sich das
        # Fenster (Seitenleiste auf/zu) in der Breite aendert.
        self.rahmen.place(x=0, y=y, relwidth=1.0)
        self.rahmen.lift()
        self.markiert = -1
        return True

    def _markieren(self, nummer):
        self.markiert = nummer
        for i, (zeile, _) in enumerate(self.zeilen):
            zeile.configure(fg_color=farben.MARKIERT if i == nummer else "transparent")

    def _waehlen(self, anfrage):
        self.schliessen()
        self.suchfeld.delete(0, "end")
        self.suchfeld.insert(0, anfrage)
        self.bei_auswahl(anfrage)

    def _loeschen(self):
        self.schliessen()
        self.bei_loeschen()
        try:
            self.suchfeld.focus_set()
        except Exception:
            pass
