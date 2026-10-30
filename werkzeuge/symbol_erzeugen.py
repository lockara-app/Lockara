"""Erzeugt alle App-Symbole aus dem Lockara-Maskottchen.

Quelle ist ressourcen/icons/maskottchen.svg (Schluesselloch mit grossen
Augen, #0A0F1A auf #FF6A2B - dasselbe Bild wie auf lockara.de und als
TikTok/Instagram-Profilbild). Weil auf dem Mac kein SVG-Renderer
mitgeliefert wird, zeichnet dieses Skript die wenigen Formen des SVG mit
Pillow nach (gleiche Koordinaten, 1080er Raster) - jede Groesse wird
einzeln und mit 8-facher Ueberabtastung gezeichnet, damit auch 16 px
scharf bleiben.

Ergebnis in ressourcen/icons/:
  icon.icns              Mac-App (macOS-Raster: Squircle mit Rand und Schatten)
  icon.png               1024 px, Mac-Stil (Dock-Symbol zur Laufzeit, Tray-Ersatz)
  icon.ico               Windows (randlos abgerundetes Quadrat, 16-256 px)
  menueleiste_vorlage.png  einfarbiges Template-Bild fuer die Mac-Menueleiste

Aufruf:  venv/bin/python werkzeuge/symbol_erzeugen.py
"""
import os
import shutil
import subprocess
import tempfile

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ORDNER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "ressourcen", "icons")

ORANGE = (0xFF, 0x6A, 0x2B, 255)
NACHT = (0x0A, 0x0F, 0x1A, 255)
WEISS = (255, 255, 255, 255)
UEBER = 8  # Ueberabtastung


def _quad(p0, p1, p2, schritte=24):
    """Punkte einer quadratischen Bezierkurve (wie 'Q' im SVG-Pfad)."""
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1])
            for t in (i / schritte for i in range(schritte + 1))]


# Fuss des Schluessellochs: M430 600 L650 600 L728 858 Q738 892 702 892
#                           L378 892 Q342 892 352 858 Z
FUSS = ([(430, 600), (650, 600), (728, 858)] + _quad((728, 858), (738, 892), (702, 892))
        + [(378, 892)] + _quad((378, 892), (342, 892), (352, 858)))
LAECHELN = _quad((496, 560), (540, 600), (584, 560), 64)


def _maskottchen(d, ox, oy, k, klein=False):
    """Zeichnet das Maskottchen (1080er Koordinaten) mit Versatz ox/oy und Massstab k.
    klein=True (16 px): nur weisse Augen, ohne Pupillen und Laecheln - die
    wuerden bei 16 px zu einem grauen Fleck verschwimmen."""
    P = lambda x, y: (ox + x * k, oy + y * k)
    kreis = lambda cx, cy, rx, ry, f: d.ellipse(
        [P(cx - rx, cy - ry), P(cx + rx, cy + ry)], fill=f)
    kreis(540, 455, 235, 235, NACHT)
    d.polygon([P(x, y) for x, y in FUSS], fill=NACHT)
    for cx in (452, 628):
        kreis(cx, 435, 64, 78, WEISS)
    if klein:
        return
    for cx in (470, 646):
        kreis(cx, 421, 36, 36, NACHT)
    for cx in (482, 658):
        kreis(cx, 408, 11, 11, WEISS)
    for x, y in LAECHELN:  # Strich 18 breit mit runden Enden
        kreis(x, y, 9, 9, WEISS)


def _squircle(n_px, rand, exponent=5.0, punkte=720):
    """Polygon der macOS-Kachelform (Superellipse) im Quadrat [rand, n_px-rand]."""
    import math
    m = n_px / 2
    r = m - rand
    pts = []
    for i in range(punkte):
        a = 2 * math.pi * i / punkte
        c, s = math.cos(a), math.sin(a)
        x = math.copysign(abs(c) ** (2 / exponent), c)
        y = math.copysign(abs(s) ** (2 / exponent), s)
        pts.append((m + r * x, m + r * y))
    return pts


def _verkleinern(bild, px):
    """Flaechenmittel auf vormultipliziertem Alpha: kein Nachschwingen
    (LANCZOS erzeugte einen orangen Saum um die 16-px-Kachel)."""
    return bild.convert("RGBa").resize((px, px), Image.BOX).convert("RGBA")


def mac_symbol(px):
    """macOS-Raster (Big Sur und neuer): 1024er Leinwand, Kachel 824x824 mit
    100 Rand, leichter Schlagschatten nach unten."""
    n = px * UEBER
    s = n / 1024
    kachel = 824 * s
    rand = 100 * s
    # Schatten
    maske = Image.new("L", (n, n), 0)
    ImageDraw.Draw(maske).polygon(_squircle(n, rand), fill=255)
    schatten = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    schatten.putalpha(maske.point(lambda v: v * 0.30))
    schatten = ImageChops.offset(schatten, 0, int(10 * s)).filter(
        ImageFilter.GaussianBlur(12 * s))
    # Kachel mit Maskottchen, auf die Squircle-Form zugeschnitten
    flaeche = Image.new("RGBA", (n, n), ORANGE)
    _maskottchen(ImageDraw.Draw(flaeche), rand, rand, kachel / 1080, klein=px <= 16)
    bild = schatten
    bild.paste(flaeche, (0, 0), maske)
    return _verkleinern(bild, px)


def windows_symbol(px):
    """Windows: randlos wie das Favicon von lockara.de (rx 250 von 1080),
    ohne Schatten - Windows zeichnet keine eigenen Kacheln."""
    n = px * UEBER
    bild = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(bild)
    d.rounded_rectangle([0, 0, n - 1, n - 1], radius=n * 250 / 1080, fill=ORANGE)
    _maskottchen(d, 0, 0, n / 1080, klein=px <= 16)
    return _verkleinern(bild, px)


def menueleisten_vorlage(pt=18, faktor=2):
    """Template-Bild fuer die Menueleiste: nur Schwarz + Transparenz, macOS
    faerbt es selbst passend zur hellen/dunklen Leiste. Schluesselloch als
    Silhouette, Augen als ausgestanzte Loecher mit Pupille - das Laecheln
    entfaellt, bei 18 pt waere es nur ein Pixelstrich."""
    px = pt * faktor
    n = px * UEBER
    # Schluesselloch reicht von y=220 bis 892 (672 hoch), x von ~342 bis 738
    k = n * 0.94 / 672
    ox = n / 2 - 540 * k
    oy = n / 2 - 556 * k
    maske = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(maske)
    P = lambda x, y: (ox + x * k, oy + y * k)
    oval = lambda cx, cy, rx, ry, f: d.ellipse([P(cx - rx, cy - ry), P(cx + rx, cy + ry)], fill=f)
    oval(540, 455, 235, 235, 255)
    d.polygon([P(x, y) for x, y in FUSS], fill=255)
    for cx in (452, 628):
        oval(cx, 435, 70, 84, 0)
    for cx in (470, 646):
        oval(cx, 425, 34, 34, 255)
    bild = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    bild.putalpha(maske)
    return _verkleinern(bild, px)


def main():
    # macOS: .iconset -> .icns ueber Apples iconutil
    tmp = tempfile.mkdtemp()
    iconset = os.path.join(tmp, "icon.iconset")
    os.mkdir(iconset)
    for basis in (16, 32, 128, 256, 512):
        mac_symbol(basis).save(os.path.join(iconset, f"icon_{basis}x{basis}.png"))
        mac_symbol(basis * 2).save(os.path.join(iconset, f"icon_{basis}x{basis}@2x.png"))
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o",
                    os.path.join(ORDNER, "icon.icns")], check=True)
    shutil.rmtree(tmp)

    mac_symbol(1024).save(os.path.join(ORDNER, "icon.png"))

    groessen = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    bilder = [windows_symbol(g) for g in groessen]
    bilder[-1].save(os.path.join(ORDNER, "icon.ico"), format="ICO",
                    sizes=[(g, g) for g in groessen], append_images=bilder[:-1])

    menueleisten_vorlage().save(os.path.join(ORDNER, "menueleiste_vorlage.png"))
    print("Symbole geschrieben nach", ORDNER)


if __name__ == "__main__":
    main()
