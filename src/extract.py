import logging
import requests
import re
import os
import urllib.parse
from bs4 import BeautifulSoup
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


def extraer_precios_ebay(
    query: str = "tarjeta grafica",
    site_id: str = "ES",
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Recupera información pública de listados de productos y precios desde eBay España.
    Realiza la extracción a partir del HTML público enrutado por ScraperAPI para evitar bloqueos.
    
    Args:
        query (str): Término de búsqueda.
        site_id (str): Identificador regional (por defecto ES para España).
        limit (int): Número máximo de registros a recuperar.
        
    Returns:
        List[Dict[str, Any]]: Lista de registros con la información recuperada.
    """
    query_encoded = urllib.parse.quote_plus(query)
    # URL de búsqueda de eBay España
    url = f"https://www.ebay.es/sch/i.html?_nkw={query_encoded}"
    
    logger.info(f"Sincronizando listado de productos de eBay: {url} (Límite: {limit})...")
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    })
    
    try:
        scraper_api_key = os.getenv("SCRAPER_API_KEY")
        if scraper_api_key:
            logger.info("Enrutando petición a través del proxy residencial de ScraperAPI (Estándar)...")
            payload = {'api_key': scraper_api_key, 'url': url}
            response = session.get('http://api.scraperapi.com', params=payload, timeout=60)
        else:
            logger.warning("No se detectó SCRAPER_API_KEY. Intentando petición directa (puede ser bloqueado)...")
            response = session.get(url, timeout=15)
            
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Buscar el contenedor principal de resultados (el ul)
        results_ul = soup.select_one("ul.srp-results")
        items = results_ul.select("li.s-item, li") if results_ul else []
        
        if not items:
            logger.warning(f"No se pudieron estructurar los elementos del catálogo (Largo HTML: {len(response.text)}). Grabando inspect_ebay.html...")
            with open("inspect_ebay.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            return []
            
        datos_crudos = []
        for item in items:
            try:
                title_el = item.select_one(".s-item__title") or item.select_one("[class*='title']")
                price_el = item.select_one(".s-item__price") or item.select_one("[class*='price']")
                link_el = item.select_one(".s-item__link") or item.select_one("a[href]")
                
                if not title_el or not price_el or not link_el:
                    continue
                
                title = title_el.text.replace("Anuncio nuevo", "").replace("Se abre en una nueva ventana o pestaña", "").strip()
                if "comprar por" in title.lower() or "shop on" in title.lower() or not title:
                    continue
                
                price_text = price_el.text.strip()
                match = re.search(r"[\d\.\,]+", price_text)
                if not match:
                    continue
                
                num_str = match.group(0)
                if "," in num_str:
                    num_str = num_str.replace(".", "").replace(",", ".")
                precio_actual = float(num_str)
                
                url_producto = link_el.get("href")
                if not url_producto or "http" not in url_producto:
                    continue
                    
                # Extraer ID único de producto desde la URL de eBay
                match_id = re.search(r"/itm/(\d+)", url_producto)
                if match_id:
                    producto_id = f"EBAY_{match_id.group(1)}"
                else:
                    producto_id = f"REF_{abs(hash(title))}"
                
                datos_crudos.append({
                    "producto_id": producto_id,
                    "nombre": title,
                    "precio_actual": precio_actual,
                    "disponible": True,
                    "url_producto": url_producto
                })
                
                if len(datos_crudos) >= limit:
                    break
            except Exception as item_err:
                logger.warning(f"Error al procesar el ítem individual: {item_err}")
                continue
                
        logger.info(f"Sincronización finalizada. Recuperados {len(datos_crudos)} registros válidos.")
        return datos_crudos
        
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"Error HTTP durante la sincronización: {http_err}")
        raise
    except Exception as e:
        logger.error(f"Error general durante el procesamiento: {e}")
        raise

# Mantener compatibilidad con main.py
extraer_precios_mercadolibre = extraer_precios_ebay

if __name__ == "__main__":
    print("--- [TEST] Prueba Local del Pipeline de Extracción (eBay España) ---")
    try:
        resultados = extraer_precios_ebay(query="tarjeta grafica", limit=3)
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
