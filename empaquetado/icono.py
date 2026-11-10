"""Crea el ícono de la app a partir de la ilustración oficial de Hatsune Miku.

Ilustración: Hatsune Miku, © Crypton Future Media, Inc. 2007 — CC BY-NC 3.0 (ver arte/LICENCIA-miku.txt).
Adaptación: recorte de la cara, fondo azul "noche" e insignia de descarga.

Genera:
  empaquetado/icono.ico              (exe e instalador)
  empaquetado/icono.png              (512 px, referencia)
  app/descargador/ui/logo.png        (128 px, cabecera de la ventana)
"""

from pathlib import Path

from PIL import Image, ImageDraw

AQUI = Path(__file__).parent
UI = AQUI.parent / "app" / "descargador" / "ui"
G = 1024
MARGEN = 40
FONDO = ((51, 65, 85), (15, 23, 42))   # slate 700 → slate 900
ACENTO = (15, 118, 110)                 # teal 700, el mismo de la app
RECORTE = (150, 0, 350, 200)            # cara y audífonos en la ilustración de 519×791


def degradado(t: int) -> Image.Image:
    (a, b) = FONDO
    img = Image.new("RGBA", (t, t))
    d = ImageDraw.Draw(img)
    for y in range(t):
        k = y / (t - 1)
        d.line([(0, y), (t, y)], fill=tuple(round(x + (z - x) * k) for x, z in zip(a, b)) + (255,))
    return img


def insignia(d: ImageDraw.ImageDraw) -> None:
    r = 170
    cx = cy = G - MARGEN - r - 30
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="white")
    d.ellipse([cx - r + 18, cy - r + 18, cx + r - 18, cy + r - 18], fill=ACENTO + (255,))
    g = 44
    d.line([(cx, cy - 90), (cx, cy + 40)], fill="white", width=g)
    d.line([(cx - 75, cy - 15), (cx, cy + 60)], fill="white", width=g)
    d.line([(cx + 75, cy - 15), (cx, cy + 60)], fill="white", width=g)
    d.line([(cx - 85, cy + 105), (cx + 85, cy + 105)], fill="white", width=g)


def dibujar() -> Image.Image:
    miku = Image.open(AQUI / "arte" / "miku-oficial.png").convert("RGBA")
    fondo = degradado(G)
    cara = miku.crop(RECORTE).resize((G - 2 * MARGEN, G - 2 * MARGEN), Image.LANCZOS)
    fondo.alpha_composite(cara, (MARGEN, MARGEN))
    insignia(ImageDraw.Draw(fondo))
    mascara = Image.new("L", (G, G), 0)
    ImageDraw.Draw(mascara).rounded_rectangle([MARGEN, MARGEN, G - MARGEN, G - MARGEN], radius=220, fill=255)
    lienzo = Image.new("RGBA", (G, G), (0, 0, 0, 0))
    lienzo.paste(fondo, (0, 0), mascara)
    return lienzo


if __name__ == "__main__":
    img = dibujar()
    img.resize((512, 512), Image.LANCZOS).save(AQUI / "icono.png")
    img.resize((128, 128), Image.LANCZOS).save(UI / "logo.png")
    img.save(AQUI / "icono.ico", sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48),
                                         (64, 64), (128, 128), (256, 256)])
    print("icono.ico, icono.png y ui/logo.png listos")
