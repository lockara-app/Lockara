#!/usr/bin/env python3
"""Prueft die Umrechnung von Mausrad- und Trackpad-Ereignissen
(oberflaeche/rollen.py). Ohne Fenster, laeuft ueberall.

    python -m tests.test_rollen
"""
import sys
import types

from lockara.oberflaeche import rollen

R = rollen.PIXEL_JE_RASTE
M = rollen.PIXEL_JE_MAC_EINHEIT


def tp(dx, dy):
    """So packt Tk 9 die Trackpad-Abstaende in %D."""
    return ((dx & 0xFFFF) << 16) | (dy & 0xFFFF)


FAELLE = [
    # (Beschreibung, Ereignis-delta, art, erwartete Pixel nach unten)
    ("Tk 9 / Windows: eine Raste nach unten", -120, "rad", R),
    ("Tk 9 / Windows: eine Raste nach oben", 120, "rad", -R),
    ("Tk 9 / Windows: drei Rasten", -360, "rad", 3 * R),
    ("Tk 8.6 Mac: kleiner Wert nach unten", -2, "rad", 2 * M),
    ("Tk 8.6 Mac: kleiner Wert nach oben", 3, "rad", -3 * M),
    ("kein Wert", 0, "rad", 0),
    ("Trackpad nach unten (Finger nach oben)", tp(0, -15), "touchpad", 15),
    ("Trackpad nach oben", tp(0, 7), "touchpad", -7),
    ("Trackpad seitlich und runter", tp(-4, -9), "touchpad", 9),
    ("Trackpad nur seitlich", tp(12, 0), "touchpad", 0),
    ("Linux Knopf 4", 0, "hoch", -R),
    ("Linux Knopf 5", 0, "runter", R),
]


def main():
    fehler = 0
    for text, delta, art, soll in FAELLE:
        ist = rollen.pixel_aus_ereignis(types.SimpleNamespace(delta=delta), art)
        if ist != soll:
            fehler += 1
            print(f"FALSCH  {text}: {ist} statt {soll}")
    if rollen.touchpad_deltas(tp(-3, 5)) != (-3, 5):
        fehler += 1
        print("FALSCH  touchpad_deltas zerlegt nicht richtig")
    print("Alle Rollfaelle wie erwartet." if not fehler else f"{fehler} Fehler")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
