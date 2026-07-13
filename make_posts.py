#!/usr/bin/env python3
"""
Genera posts verticales (1080x1920) estilo editorial, uno por marca, con los
productos DISPONIBLES. Lee docs/data.json y escribe docs/posts/<marca>.png.
"""
from __future__ import annotations

import io
import json
import unicodedata
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import config

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "assets" / "fonts"
DOCS = ROOT / "docs"
# Los posts se guardan en tu PC (carpeta en VENTA_CA), NO se publican en la web.
POSTS = ROOT.parent / "Posts LU STORE"
# Stock más actual: se lee del catálogo en línea; si no hay internet, del archivo local.
LIVE_DATA = "https://luzanco.github.io/lu-store/data.json"

W, H = 1080, 1920
BG = (229, 225, 218)      # crema/gris cálido
INK = (30, 27, 25)
WHITE = (255, 255, 255)
HANDLE = "luzanco.github.io/lu-store"

# --- fuentes ---
def playfair(size, weight=700, italic=False):
    f = ImageFont.truetype(str(FONTS / ("PlayfairDisplay-Italic-var.ttf" if italic
                                        else "PlayfairDisplay-var.ttf")), size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f

def poppins(size, name="Poppins-SemiBold.ttf"):
    return ImageFont.truetype(str(FONTS / name), size)


# --- imágenes ---
_cache: dict[str, Image.Image] = {}
def load_img(url):
    if url not in _cache:
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        _cache[url] = Image.open(io.BytesIO(r.content)).convert("RGB")
    return _cache[url].copy()

def cover(im, w, h):
    sr, ir = w / h, im.width / im.height
    if ir > sr:
        nw = int(im.height * sr); x = (im.width - nw) // 2
        im = im.crop((x, 0, x + nw, im.height))
    else:
        nh = int(im.width / sr); y = (im.height - nh) // 2
        im = im.crop((0, y, im.width, y + nh))
    return im.resize((w, h), Image.LANCZOS)


# --- texto ---
def tracked(draw, cx, y, text, font, fill, tracking, center=True):
    ws = [draw.textlength(c, font=font) for c in text]
    total = sum(ws) + tracking * (len(text) - 1)
    x = cx - total / 2 if center else cx
    for c, w in zip(text, ws):
        draw.text((x, y), c, font=font, fill=fill)
        x += w + tracking
    return total

def fit_font(draw, text, maxw, start, weight=800):
    size = start
    while size > 40:
        f = playfair(size, weight)
        if draw.textlength(text, font=f) <= maxw:
            return f
        size -= 4
    return playfair(size, weight)


def paste_card(canvas, im, w, h, angle, cx, cy):
    """Pega la foto con marco blanco y sombra. Devuelve (cx, bottom_y) para el precio."""
    border = 16
    photo = cover(im, w, h)
    base = Image.new("RGBA", (w + border * 2, h + border * 2), (255, 255, 255, 255))
    base.paste(photo, (border, border))
    rot = base.rotate(angle, expand=True, resample=Image.BICUBIC)
    x, y = int(cx - rot.width / 2), int(cy - rot.height / 2)
    sh = Image.new("RGBA", rot.size, (0, 0, 0, 0))
    sh.putalpha(rot.split()[3].point(lambda a: 90 if a > 0 else 0))
    sh = sh.filter(ImageFilter.GaussianBlur(16))
    canvas.alpha_composite(sh, (x + 6, y + 14))
    canvas.alpha_composite(rot, (x, y))
    return cx, y + rot.height


def draw_price(canvas, cx, bottom_y, price):
    d = ImageDraw.Draw(canvas)
    f = poppins(30, "Poppins-Bold.ttf")
    tw = d.textlength(price, font=f)
    pw, ph = tw + 34, 52
    px, py = int(cx - pw / 2), int(bottom_y - ph - 6)
    d.rounded_rectangle([px, py, px + pw, py + ph], radius=26, fill=(30, 27, 25, 235))
    d.text((px + pw / 2, py + ph / 2), price, font=f, fill=WHITE, anchor="mm")


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


LAYOUT = [  # (w, h, angle, cx, cy)
    (450, 560, -5, 372, 900),
    (360, 450, 6, 762, 726),
    (356, 448, 4, 360, 1332),
    (430, 540, -6, 754, 1320),
]

def make_post(brand, products, out):
    canvas = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(canvas)

    # --- encabezado ---
    tracked(d, W / 2, 118, "LU STORE", poppins(30, "Poppins-SemiBold.ttf"), (120, 110, 100), 14)
    d.text((W / 2, 250), brand, font=playfair(140, 520, italic=True), fill=INK, anchor="mm")
    big = fit_font(d, "DISPONIBLE", 900, 176, weight=850)
    d.text((W / 2, 380), "DISPONIBLE", font=big, fill=INK, anchor="mm")

    # --- collage (primero todas las fotos, luego todos los precios encima) ---
    pending = []
    for (w, h, ang, cx, cy), p in zip(LAYOUT, products):
        try:
            im = load_img(p["images"][0])
        except Exception as e:
            print("  img err:", e); continue
        bx, by = paste_card(canvas, im, w, h, ang, cx, cy)
        pending.append((bx, by, f"S/ {int(p['price'])}"))
    for bx, by, price in pending:
        draw_price(canvas, bx, by, price)

    # --- pie ---
    f = poppins(30, "Poppins-SemiBold.ttf")
    label = "LU STORE  ·  " + HANDLE
    tw = d.textlength(label, font=f)
    pw, ph = tw + 70, 74
    px, py = int(W / 2 - pw / 2), 1770
    d.rounded_rectangle([px, py, px + pw, py + ph], radius=37, fill=WHITE)
    d.text((W / 2, py + ph / 2), label, font=f, fill=INK, anchor="mm")

    canvas.convert("RGB").save(out, "PNG")
    print("  ->", out)


def brand_key(b):
    return strip_accents(b).lower().replace(" ", "-")


def write_gallery(generated):
    """generated: lista de (marca, archivo). Escribe docs/posts/index.html para descargar."""
    import datetime
    dia = datetime.datetime.now().weekday()  # 0=lunes
    hoy = generated[dia % len(generated)][0] if generated else ""
    cards = ""
    for brand, fn in generated:
        tag = ' <span class="hoy">Sugerido hoy</span>' if brand == hoy else ""
        cards += f'''
      <figure>
        <img src="{fn}" alt="{brand}" loading="lazy">
        <figcaption>{brand}{tag}</figcaption>
        <a class="dl" href="{fn}" download="LU-STORE-{fn}">⬇ Descargar</a>
      </figure>'''
    html = f'''<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Posts · LU STORE</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:"Segoe UI",system-ui,sans-serif;background:#14110e;color:#f2ede8;text-align:center}}
  header{{padding:22px 16px 6px}} h1{{font-size:1.4rem;letter-spacing:.5px}}
  p.sub{{color:#a89c93;font-size:.85rem;padding:2px 20px 4px}}
  a.back{{display:inline-block;color:#e7c8d2;font-size:.8rem;margin:8px;text-decoration:none}}
  .grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;padding:14px;max-width:820px;margin:0 auto}}
  @media(min-width:620px){{.grid{{grid-template-columns:repeat(3,1fr)}}}}
  figure{{background:#211c18;border-radius:14px;overflow:hidden;padding-bottom:10px}}
  figure img{{width:100%;display:block}}
  figcaption{{font-size:.85rem;padding:8px 6px 4px;font-weight:600}}
  .hoy{{display:inline-block;background:#a6224d;color:#fff;font-size:.62rem;font-weight:700;
        padding:2px 7px;border-radius:999px;vertical-align:middle;margin-left:4px}}
  a.dl{{display:inline-block;margin-top:4px;background:#25d366;color:#fff;text-decoration:none;
        font-weight:700;font-size:.8rem;padding:7px 16px;border-radius:9px}}
  footer{{color:#a89c93;font-size:.75rem;padding:18px 16px 34px}}
</style></head><body>
  <header>
    <h1>Posts para tus redes</h1>
    <p class="sub">Toca <b>Descargar</b> (o mantén presionada la foto → “Guardar imagen”) y súbela a tu Estado o Historia.</p>
    <a class="back" href="../">← Volver al catálogo</a>
  </header>
  <main class="grid">{cards}
  </main>
  <footer>LU STORE · se actualizan solos con los productos disponibles</footer>
</body></html>'''
    (POSTS / "index.html").write_text(html, encoding="utf-8")
    print("Galería:", POSTS / "index.html")


def load_data():
    try:
        r = requests.get(LIVE_DATA, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        print("Usando stock en línea (más actual).")
        return r.json()
    except Exception:
        print("Sin internet: usando datos locales.")
        return json.load(open(DOCS / "data.json", encoding="utf-8"))


def main(only=None):
    data = load_data()
    prods = [p for p in data["products"] if p.get("images")]
    brands: dict[str, list] = {}
    for p in prods:
        brands.setdefault(p["brand"], []).append(p)

    POSTS.mkdir(parents=True, exist_ok=True)
    order = ["Guess", "Tommy Hilfiger", "Nautica", "Steve Madden", "Juicy Couture", "Karl Lagerfeld", "Michael Kors"]
    avail = [b for b in brands if b != "Otras marcas" and len(brands[b]) >= 3]
    targets = only or [b for b in order if b in avail] + [b for b in avail if b not in order]

    generated = []
    for b in targets:
        items = brands.get(b, [])[:4]
        if len(items) < 3:
            continue
        title = b.split()[0] if " " in b else b
        fn = f"{brand_key(b)}.png"
        print(f"Post {b}: {len(items)} productos")
        make_post(title, items, POSTS / fn)
        generated.append((b, fn))

    if not only:
        write_gallery(generated)


if __name__ == "__main__":
    import sys
    main(sys.argv[1:] or None)
