#!/usr/bin/env python3
"""
rollen.py - Mausrad und Trackpad fuer die Trefferliste.

WARUM ES DAS GIBT
-----------------
Tk liefert Rollbewegungen je nach Fassung und System voellig verschieden:

- Tk 8.6 auf dem Mac: <MouseWheel> mit kleinen Werten (1, 2, 3 ...) - auch
  fuer das Trackpad.
- Tk 8.6 unter Windows: <MouseWheel> mit Vielfachen von 120 je Raste.
- Tk 9 (Python 3.14 vom python.org-Installer, also die fertige App): das
  Mausrad meldet ebenfalls Vielfache von 120, und das TRACKPAD meldet sich
  gar nicht mehr als <MouseWheel>, sondern als eigenes <TouchpadScroll>
  mit Pixel-Abstaenden fuer x und y in EINER Zahl.
- Linux: <Button-4> / <Button-5> ohne Wert.

Die Trefferliste kannte bisher nur die erste Variante. In der App (Tk 9)
rollte das Trackpad deshalb gar nicht, und eine Mausrad-Raste (120) sprang
ans Listenende. Hier wird alles auf Pixel umgerechnet; die Liste rollt mit
yscrollincrement=1 pixelgenau.
"""

# Pixel je Mausrad-Raste.
PIXEL_JE_RASTE = 48
# Tk 8.6 auf dem Mac liefert pro Ereignis kleine Werte - ungefaehr Zeilen.
PIXEL_JE_MAC_EINHEIT = 12


def _vorzeichen16(wert):
    wert &= 0xFFFF
    return wert - 0x10000 if wert & 0x8000 else wert


def touchpad_deltas(delta):
    """Zerlegt den %D-Wert eines <TouchpadScroll>-Ereignisses (Tk 9) in
    (dx, dy) Pixel - wie tk::PreciseScrollDeltas: obere 16 Bit x, untere
    16 Bit y, beide mit Vorzeichen."""
    return _vorzeichen16(delta >> 16), _vorzeichen16(delta)


def mausrad_pixel(delta):
    """Pixel, um die die Liste bei einem <MouseWheel>-Ereignis nach UNTEN
    rollen soll (negativ = nach oben)."""
    if not delta:
        return 0
    if abs(delta) >= 120:
        # Windows und Tk 9: 120 je Raste, feine Raeder auch Bruchteile.
        return round(-delta / 120 * PIXEL_JE_RASTE)
    # Tk 8.6 auf dem Mac (Rad und Trackpad).
    return -delta * PIXEL_JE_MAC_EINHEIT


def pixel_aus_ereignis(ereignis, art):
    """art: "rad", "touchpad", "hoch" (Button-4) oder "runter" (Button-5)."""
    if art == "touchpad":
        _, dy = touchpad_deltas(int(getattr(ereignis, "delta", 0) or 0))
        return -dy
    if art == "hoch":
        return -PIXEL_JE_RASTE
    if art == "runter":
        return PIXEL_JE_RASTE
    return mausrad_pixel(int(getattr(ereignis, "delta", 0) or 0))


def einrichten(canvas):
    """Stellt die Liste auf pixelgenaues Rollen um. Die Pfeiltasten-
    Navigation rollt per yview_moveto und ist davon nicht betroffen."""
    canvas.configure(yscrollincrement=1)


def rollen(canvas, pixel):
    if pixel:
        canvas.yview_scroll(int(pixel), "units")


def binden(widget, rueckruf, alle=False):
    """Bindet alle Rollereignisse an rueckruf(ereignis, art). alle=True
    bindet fuer die ganze Anwendung (bind_all). <TouchpadScroll> gibt es
    erst ab Tk 9 - auf aelteren Fassungen wird es still uebergangen."""
    binder = widget.bind_all if alle else widget.bind
    for sequenz, art in (("<MouseWheel>", "rad"), ("<Button-4>", "hoch"),
                         ("<Button-5>", "runter"), ("<TouchpadScroll>", "touchpad")):
        try:
            binder(sequenz, lambda e, a=art: rueckruf(e, a))
        except Exception:
            pass
