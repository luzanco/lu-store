# LU STORE — catálogo web

Catálogo web propio que se **actualiza solo** cada 5 minutos (GitHub Actions) y se publica gratis
en GitHub Pages.

**Página:** https://luzanco.github.io/lu-store/

## Configuración
- Los datos de presentación (marca, color) están en **`config.py`**.
- Los **datos sensibles** (fuente de productos y margen) NO están en el código: se guardan como
  **Secrets** del repositorio (Settings → Secrets and variables → Actions):
  `STORE_SLUG`, `MARKUP` y opcionalmente `CATEGORY`.

## Probar en tu PC (opcional)
```bash
pip install -r requirements.txt
STORE_SLUG=... MARKUP=13 python build_catalog.py   # define tus variables
```
Luego abre `docs/index.html`.

## Notas
- La página se actualiza ~cada 5 min (GitHub Actions; a veces se demora un poco más).
- Si la fuente de datos cambia su diseño, `build_catalog.py` podría necesitar un ajuste.
