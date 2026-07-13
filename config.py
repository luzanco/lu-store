import os

# =============================================================================
#  CONFIGURACIÓN DE TU CATÁLOGO
# =============================================================================

# --- Tu marca (esto SÍ es público: aparece en la cabecera del catálogo) ---
BRAND    = os.environ.get("BRAND",   "LU STORE")
TAGLINE  = os.environ.get("TAGLINE", "Originales USA · Carteras y accesorios")
COLOR    = os.environ.get("COLOR",   "#a6224d")   # color principal de tu marca

# --- Presentación ---
CURRENCY     = "S/"
AVAILABILITY = "in_stock,soon,pre_sale"   # Disponible + Preventa + Pronto

# --- WhatsApp (botón "Pedir por WhatsApp" en cada producto) ---
# Tu número CON código de país y SIN símbolos, ej. Perú: 51987654321
# Déjalo vacío ("") para ocultar el botón.
WHATSAPP     = os.environ.get("WHATSAPP", "")
WHATSAPP_MSG = "¡Hola LU STORE! Me interesa este producto:"

# =============================================================================
#  🔐 DATOS SENSIBLES  —  NO se escriben aquí.
#  Vienen de los "Secrets" de GitHub (caja fuerte cifrada), así tu proveedor
#  y tu ganancia quedan OCULTOS aunque el repositorio sea público.
#    STORE_SLUG = identificador de la tienda proveedora
#    MARKUP     = soles que sumas a cada precio
#  Para probar en tu PC, define esas variables de entorno antes de ejecutar.
# =============================================================================
STORE_SLUG = os.environ.get("STORE_SLUG", "")
MARKUP     = float(os.environ.get("MARKUP", "0"))
CATEGORY   = os.environ.get("CATEGORY") or None   # None = toda la tienda
