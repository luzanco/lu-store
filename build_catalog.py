#!/usr/bin/env python3
"""
Construye un catálogo propio a partir de la tienda proveedora en Arlessa.

- Descarga todas las páginas de productos disponibles del proveedor.
- Mapea cada producto a sus categorías y marca.
- Le suma tu recargo (MARKUP) a cada precio.
- Genera docs/index.html (tu catálogo con filtros) y docs/data.json.

No requiere ninguna API: lee el HTML público de la tienda.
Edita la configuración en config.py, no aquí.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape

import config

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
BASE_URL = f"https://app.arlessa.com/s/{config.STORE_SLUG}/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; catalogo-bot/1.0)"}
PERU_TZ = timezone(timedelta(hours=-5))  # America/Lima

# Estado del proveedor -> etiqueta visible + clase de color
STATUS_MAP = {
    "disponible": ("Disponible", "ok"),
    "preventa":   ("Preventa",   "pre"),
    "pre-venta":  ("Preventa",   "pre"),
    "pronto":     ("Pronto",     "soon"),
    "próximamente": ("Pronto",   "soon"),
    "proximamente": ("Pronto",   "soon"),
}

# Marcas reconocidas en los nombres de producto (minúsculas)
BRANDS = {
    "guess": "Guess", "tommy": "Tommy Hilfiger", "juicy": "Juicy Couture",
    "steve madden": "Steve Madden", "karl lagerfeld": "Karl Lagerfeld",
    "michael kors": "Michael Kors", "nautica": "Nautica",
}


SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def get(url: str, params: dict) -> str:
    r = SESSION.get(url, params=params, timeout=30)
    r.raise_for_status()
    time.sleep(0.2)  # cortesía con el servidor del proveedor
    return r.text


def fetch_gallery(pid: str) -> list[str]:
    """Todas las fotos del producto (desde su página de detalle), en orden."""
    try:
        html = get(BASE_URL + f"p/{pid}/", {})
    except requests.RequestException:
        return []
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find(attrs={"data-store-carousel-root": True}) or soup
    urls: list[str] = []
    for item in root.select("[data-store-carousel-item] img"):
        src = item.get("src")
        # usar la URL exacta del proveedor (las variantes forzadas dan 403)
        if src and "digitaloceanspaces" in src and src not in urls:
            urls.append(src)
    return urls


def product_ids(html: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    ids = set()
    for a in soup.select('a[href*="/p/prod-"]'):
        if not a.find("h2"):
            continue
        m = re.search(r"/p/(prod-[A-Za-z0-9-]+)/", a["href"])
        if m:
            ids.add(m.group(1))
    return ids


def fetch_categories() -> dict[str, str]:
    """Devuelve {cat-id: nombre} desde el endpoint de filtro de categorías."""
    try:
        html = get(BASE_URL + "category-filter/", {})
    except requests.RequestException as e:
        print(f"[warn] no se pudo leer categorías: {e}", file=sys.stderr)
        return {}
    soup = BeautifulSoup(html, "html.parser")
    cats = {}
    for inp in soup.find_all("input"):
        val = inp.get("value", "")
        if val.startswith("cat-"):
            lbl = inp.find_parent("label")
            name = lbl.get_text(" ", strip=True) if lbl else ""
            if name:
                cats[val] = name
    return cats


def category_map(cats: dict[str, str]) -> dict[str, list[str]]:
    """Devuelve {prod-id: [nombres de categoría]} recorriendo cada categoría."""
    pmap: dict[str, list[str]] = {}
    for cid, cname in cats.items():
        seen: set[str] = set()
        for page in range(1, 15):
            try:
                html = get(BASE_URL, {"categories": cid,
                                      "availability_status": config.AVAILABILITY, "page": page})
            except requests.RequestException:
                break
            ids = product_ids(html)
            new = ids - seen
            if not new:
                break
            seen |= ids
            for pid in new:
                pmap.setdefault(pid, []).append(cname)
        print(f"  categoría {cname}: {len(seen)} productos")
    return pmap


def brand_for(name: str, categories: list[str]) -> str:
    n = name.lower()
    for key, label in BRANDS.items():
        if key in n:
            return label
    for c in categories:  # p. ej. "Carteras Guess" -> Guess
        for key, label in BRANDS.items():
            if key in c.lower():
                return label
    return "Otras marcas"


def parse_products(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for a in soup.select('a[href*="/p/prod-"]'):
        h2 = a.find("h2")
        if not h2:
            continue
        m = re.search(r"/p/(prod-[A-Za-z0-9-]+)/", a["href"])
        pid = m.group(1) if m else None
        name = h2.get_text(strip=True)

        price_val = None
        p = h2.find_next("p")
        if p:
            pm = re.search(r"S/\s*([\d.,]+)", p.get_text(" ", strip=True))
            if pm:
                price_val = _to_number(pm.group(1))

        card = a
        for _ in range(6):
            card = card.parent
            if card is None:
                break
            if card.find("span", class_=re.compile("badge")) and card.find("img"):
                break

        status_raw = ""
        badge = card.find("span", class_=re.compile("badge")) if card else None
        if badge:
            status_raw = badge.get_text(strip=True)
        label, css = STATUS_MAP.get(status_raw.lower(), (status_raw or "Disponible", "ok"))

        img = card.find("img") if card else None
        img_url = img.get("src") if img else None

        if not (pid and name and price_val is not None and img_url):
            continue

        items.append({
            "id": pid, "name": name,
            "price": round(price_val + config.MARKUP, 2),
            "status": label, "status_css": css, "image": img_url,
        })
    return items


def _to_number(s: str) -> float:
    s = s.strip()
    if "," in s and "." in s:
        s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)


def scrape_all() -> list[dict]:
    seen: set[str] = set()
    products: list[dict] = []
    params_extra = {"categories": config.CATEGORY} if config.CATEGORY else {}
    for page in range(1, 50):
        try:
            html = get(BASE_URL, {"availability_status": config.AVAILABILITY,
                                  "page": page, "sort": "default", **params_extra})
        except requests.RequestException as e:
            print(f"[warn] página {page}: {e}", file=sys.stderr)
            break
        page_items = parse_products(html)
        new = [it for it in page_items if it["id"] not in seen]
        print(f"  página {page}: {len(page_items)} productos ({len(new)} nuevos)")
        if not new:
            break
        for it in new:
            seen.add(it["id"])
            products.append(it)
    return products


def fmt_price(v: float) -> str:
    return f"{config.CURRENCY} {int(v)}" if float(v).is_integer() else f"{config.CURRENCY} {v:,.2f}"


def render(products: list[dict]) -> None:
    status_order = {"ok": 0, "pre": 1, "soon": 2}
    products.sort(key=lambda p: (status_order.get(p["status_css"], 9), p["name"].lower()))

    categories = sorted({c for p in products for c in p["categories"]})
    brands = sorted({p["brand"] for p in products})
    statuses = [s for s in ["Disponible", "Preventa", "Pronto"]
                if any(p["status"] == s for p in products)]

    now = datetime.now(PERU_TZ)
    env = Environment(loader=FileSystemLoader(str(ROOT / "templates")),
                      autoescape=select_autoescape(["html"]))
    env.filters["price"] = fmt_price
    html = env.get_template("catalog.html.j2").render(
        brand=config.BRAND, tagline=config.TAGLINE, color=config.COLOR,
        products=products, count=len(products),
        categories=categories, brands=brands, statuses=statuses,
        whatsapp=config.WHATSAPP, whatsapp_msg=config.WHATSAPP_MSG, currency=config.CURRENCY,
        updated=now.strftime("%d/%m/%Y %I:%M %p"))
    DOCS.mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    (DOCS / "data.json").write_text(
        json.dumps({"updated": now.isoformat(), "count": len(products), "products": products},
                   ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    print(f"Leyendo tienda {config.STORE_SLUG} (recargo +{config.MARKUP})...")
    products = scrape_all()
    print(f"Productos disponibles: {len(products)}")

    print("Mapeando categorías...")
    cats = fetch_categories()
    pmap = category_map(cats) if cats else {}

    for p in products:
        p["categories"] = pmap.get(p["id"], [])
        p["brand"] = brand_for(p["name"], p["categories"])

    print("Descargando todas las fotos de cada producto...")
    for i, p in enumerate(products, 1):
        imgs = fetch_gallery(p["id"])
        p["images"] = imgs or [p["image"]]   # fallback a la foto del listado
        p["image"] = p["images"][0]
        if i % 20 == 0:
            print(f"  {i}/{len(products)} productos con fotos")

    render(products)
    print(f"Total en catálogo: {len(products)} · Generado: {DOCS / 'index.html'}")


if __name__ == "__main__":
    main()
