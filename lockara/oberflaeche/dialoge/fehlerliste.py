#!/usr/bin/env python3
"""dialoge/fehlerliste.py - Liste der Dateien, die beim Indexieren nicht
gelesen werden konnten, mit "Erneut versuchen"."""

import customtkinter as ctk

from lockara.oberflaeche import farben
from lockara.oberflaeche.i18n import t
from lockara.kern import index


def zeigen(app):
    """Zeigt die Liste der nicht lesbaren Dateien und bietet einen
    Neuversuch-Button an (z.B. sinnvoll nach nachträglicher
    OCR-Installation - vorher musste man dafür den kompletten Index
    löschen und alles neu durchlaufen lassen)."""
    dateien = index.fehlgeschlagene_dateien()

    app.attributes("-topmost", False)
    top = ctk.CTkToplevel(app)
    top.title(t("errors.dialog_title"))
    top.geometry("560x400")
    top.attributes("-topmost", True)
    app.nebenfenster_anmelden(top)
    top.grab_set()

    lbl = ctk.CTkLabel(
        top, text=t("errors.dialog_heading", anzahl=len(dateien)),
        font=("Helvetica", 14, "bold")
    )
    lbl.pack(padx=15, pady=(15, 5), anchor="w")

    hinweis = ctk.CTkLabel(
        top,
        text=t("errors.dialog_reason"),
        font=("Helvetica", 10), text_color="#78909c", justify="left"
    )
    hinweis.pack(padx=15, pady=(0, 10), anchor="w")

    scroll = ctk.CTkScrollableFrame(top, corner_radius=8)
    scroll.pack(fill="both", expand=True, padx=15, pady=(0, 10))

    for pfad in dateien:
        ctk.CTkLabel(scroll, text=pfad, font=("Helvetica", 10), anchor="w", justify="left").pack(fill="x", pady=1)

    def neuversuch():
        # Nicht waehrend eines Laufs: der schreibt seinen eigenen Stand des
        # Index und wuerde das Entfernen der Markierungen gleich wieder
        # ueberschreiben.
        if app.indexierung_laeuft:
            app.setze_status(t("index.status_already_running"))
            return
        entfernt = index.entferne_fehlgeschlagene_markierung()
        top.destroy()
        app.aktualisiere_fehler_anzeige()
        # Gleich neu lesen, statt bis zum naechsten Lauf zu warten - wer
        # hier klickt, will das Ergebnis jetzt sehen.
        if entfernt:
            app.index_aktualisieren()
        app.setze_status(t("errors.retry_status", anzahl=entfernt))

    btn_retry = ctk.CTkButton(
        top, text=t("errors.retry_button"),
        fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER, command=neuversuch
    )
    btn_retry.pack(side="left", padx=15, pady=(0, 15))

    btn_close = ctk.CTkButton(top, text=t("errors.close_button"), command=top.destroy)
    btn_close.pack(side="right", padx=15, pady=(0, 15))
