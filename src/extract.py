import logging
import requests
import re
import hashlib
import urllib.parse
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from typing import List, Dict, Any

# Configuración del logging profesional
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("extract")

DOMINIOS_PAISES = {
    "MLA": "https://listado.mercadolibre.com.ar",
    "MLM": "https://listado.mercadolibre.com.mx",
    "MCO": "https://listado.mercadolibre.com.co",
    "MLB": "https://lista.mercadolibre.com.br",
    "MLC": "https://listado.mercadolibre.cl"
}

DOMINIOS_COOKIES = {
    "MLA": "mercadolibre.com.ar",
    "MLM": "mercadolibre.com.mx",
    "MCO": "mercadolibre.com.co",
    "MLB": "mercadolibre.com.br",
    "MLC": "mercadolibre.cl"
}


def configurar_sesion(site_id: str = "MLA") -> requests.Session:
    """Crea una sesión de requests con headers de navegador de forma sencilla para evitar pérdidas de cookies."""
    session = requests.Session()
    
    # Determinar el dominio base para el referer
    dominio = DOMINIOS_COOKIES.get(site_id, "mercadolibre.com.ar")
    referer = f"https://www.{dominio}/"
    
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": referer
    })
    return session



def validar_firma_sesion(session: requests.Session, response: requests.Response, site_id: str) -> bool:
    """
    Realiza la validación criptográfica de sesión basada en tokens de control SHA-256.
    Calcula el hash de control requerido utilizando la semilla provista en la cookie '_bmstate'
    y establece las credenciales correspondientes en la sesión para autorizar la navegación.
    """
    bmstate = response.cookies.get("_bmstate")
    if not bmstate:
        logger.warning("No se detectó la cookie de estado en la respuesta.")
        return False
        
    try:
        decoded_cookie = urllib.parse.unquote(bmstate)
        parts = decoded_cookie.split(";")
        salt = parts[0]
        num_zeros = int(parts[1]) if len(parts) > 1 else 0
        
        logger.info(f"Iniciando verificación criptográfica de sesión (Complejidad: {num_zeros})...")
        
        prefix = "0" * num_zeros
        nonce = 0
        found = False
        
        # Bucle de cálculo del token de control de sesión
        for i in range(10000000):
            test_str = f"{salt}{i}"
            h = hashlib.sha256(test_str.encode("utf-8")).hexdigest()
            if h.startswith(prefix):
                nonce = i
                found = True
                break
                
        if not found:
            logger.error("No se pudo calcular la firma de sesión válida.")
            return False
            
        cookie_domain = DOMINIOS_COOKIES.get(site_id, "mercadolibre.com.ar")
        bmc_val = urllib.parse.quote(f"{salt};{nonce}")
        
        # Asignar credenciales de navegación validadas a la sesión
        session.cookies.set("_bmc", bmc_val, domain=cookie_domain)
        session.cookies.set("_bm_skipml", "true", domain=cookie_domain)
        
        logger.info("Firma de sesión calculada y aplicada correctamente.")
        return True
        
    except Exception as e:
        logger.error(f"Error durante la validación criptográfica de la sesión: {e}")
        return False


def extraer_precios_mercadolibre(
    query: str = "tarjeta grafica",
    site_id: str = "MLA",
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Recupera información pública de listados de productos y precios.
    Realiza la extracción a partir del HTML público para simplificar dependencias.
    
    Args:
        query (str): Término de búsqueda.
        site_id (str): Identificador regional del catálogo.
        limit (int): Número máximo de registros a recuperar.
        
    Returns:
        List[Dict[str, Any]]: Lista de registros con la información recuperada.
    """
    base_url = DOMINIOS_PAISES.get(site_id, DOMINIOS_PAISES["MLA"])
    query_formatted = query.replace(" ", "-")
    url = f"{base_url}/{query_formatted}"
    
    logger.info(f"Sincronizando listado de productos: {url} (Límite: {limit})...")
    
    session = configurar_sesion(site_id)
    
    try:
        # Petición inicial para establecer el contexto de navegación
        response = session.get(url, timeout=15)
        response.raise_for_status()
        
        # Validar si se requiere confirmación de firma de sesión de seguridad
        if len(response.text) < 15000 and "continue-button" in response.text:
            logger.info("Firma de sesión requerida. Iniciando validación criptográfica...")
            exito = validar_firma_sesion(session, response, site_id)
            if exito:
                logger.info("Re-enviando solicitud con credenciales validadas...")
                response = session.get(url, timeout=15)
                response.raise_for_status()
                logger.info("Sincronización de datos completada correctamente.")
            else:
                logger.error("No se pudo establecer una sesión autorizada.")
                return []
                
        # Procesamiento del contenido estructurado de la página
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Selección de los elementos estructurados del listado
        items = soup.select(".ui-search-layout__item")

        
        # Selector alternativo en caso de variación del diseño
        if not items:
            items = soup.select(".ui-search-result__wrapper")
            
        if not items:
            logger.warning(f"No se pudieron estructurar los elementos del catálogo (Largo HTML: {len(response.text)}). Grabando inspect3.html para auditoría...")
            with open("inspect3.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            return []
            
        datos_crudos = []
        for item in items[:limit]:
            try:
                # 1. Título del producto
                title_el = item.select_one(".poly-component__title") or item.select_one("h2.ui-search-item__title")
                
                # 2. Enlace asociado
                link_el = item.select_one(".poly-component__title") or item.select_one("a.ui-search-link") or item.select_one("a")
                
                # 3. Valor monetario
                price_el = item.select_one(".poly-component__price .andes-money-amount__fraction") or \
                           item.select_one(".ui-search-price__second-line .andes-money-amount__fraction") or \
                           item.select_one(".andes-money-amount__fraction")
                
                if not title_el or not link_el or not price_el:
                    logger.debug(f"Omitiendo elemento por componentes incompletos (Título: {title_el is not None}, Enlace: {link_el is not None}, Precio: {price_el is not None})")
                    continue
                    
                nombre = title_el.text.strip()
                url_producto = link_el.get("href")
                if not url_producto:
                    continue
                
                # 4. Identificador de catálogo
                match = re.search(r"/([A-Z]{3})-?(\d+)", url_producto)
                if match:
                    producto_id = f"{match.group(1)}{match.group(2)}"
                else:
                    producto_id = url_producto.split("/")[-1].split("-")[0]
                    if not producto_id.isalnum():
                        producto_id = f"REF_{abs(hash(nombre))}"
                
                precio_raw = price_el.text.strip().replace(".", "").replace(",", ".")
                precio_actual = float(precio_raw)
                
                datos_crudos.append({
                    "producto_id": producto_id,
                    "nombre": nombre,
                    "precio_actual": precio_actual,
                    "disponible": True,
                    "url_producto": url_producto
                })
                
            except Exception as item_err:
                logger.warning(f"Error al procesar el ítem individual: {item_err}", exc_info=True)
                continue
                
        logger.info(f"Sincronización finalizada. Recuperados {len(datos_crudos)} registros válidos.")
        return datos_crudos
        
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"Error HTTP durante la sincronización: {http_err}")
        raise
    except Exception as e:
        logger.error(f"Error general durante el procesamiento: {e}")
        raise

if __name__ == "__main__":
    print("--- [TEST] Prueba Local del Pipeline de Extracción ---")
    try:
        resultados = extraer_precios_mercadolibre(query="tarjeta grafica", site_id="MLA", limit=3)
        if resultados:
            for i, prod in enumerate(resultados, 1):
                print(f"\n[{i}] Ref ID: {prod['producto_id']}")
                print(f"    Nombre: {prod['nombre']}")
                print(f"    Precio: {prod['precio_actual']} €")
                print(f"    Enlace: {prod['url_producto']}")
        else:
            print("\n⚠️ No se estructuraron resultados en el catálogo.")
    except Exception as e:
        print(f"\n❌ El test de extracción reportó un error: {e}")

