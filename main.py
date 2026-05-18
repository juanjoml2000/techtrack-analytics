import logging
import os
import sys
from dotenv import load_dotenv
from src.extract import extraer_precios_mercadolibre
from src.transform import transformar_y_analizar
from src.load import conectar_backend, sincronizar_almacenamiento_relacional

load_dotenv()

# Configuración de registro para la ejecución del pipeline
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("pipeline")

def ejecutar_pipeline():
    logger.info("=========================================")
    logger.info("INICIANDO PROCESO DE SINCRONIZACIÓN Y ANALÍTICA DE PRECIOS")
    logger.info("=========================================")
    
    # Lectura de parámetros de configuración
    query = os.getenv("SCRAPER_QUERY", "tarjeta grafica")
    site_id = os.getenv("SCRAPER_SITE_ID", "MLA")
    limit = int(os.getenv("SCRAPER_LIMIT", "10"))
    
    logger.info(f"Parámetros: Búsqueda='{query}', Región='{site_id}', Límite={limit}")
    
    try:
        # Inicialización de la sesión con la base de datos
        logger.info("Estableciendo conexión con el backend de datos...")
        supabase_client = conectar_backend()
        logger.info("Conexión de base de datos establecida.")
        
        # 1. Extracción de información (Extract)
        logger.info("--- [FASE 1: EXTRACCIÓN Y SINCRONIZACIÓN] ---")
        datos_crudos = extraer_precios_mercadolibre(query=query, site_id=site_id, limit=limit)
        
        if not datos_crudos:
            logger.warning("No se recuperaron datos de catálogo. Finalizando ejecución.")
            return
            
        # 2. Procesamiento y Análisis (Transform)
        logger.info("--- [FASE 2: PROCESAMIENTO Y ANÁLISIS EVOLUTIVO] ---")
        datos_transformados = transformar_y_analizar(datos_crudos, supabase_client)
        
        # 3. Persistencia de registros (Load)
        logger.info("--- [FASE 3: PERSISTENCIA EN ALMACENAMIENTO] ---")
        exito = sincronizar_almacenamiento_relacional(datos_transformados, supabase_client)
        
        if exito:
            logger.info("=========================================")
            logger.info("PROCESO COMPLETADO SATISFACTORIAMENTE")
            logger.info("=========================================")
        else:
            logger.error("Error durante la persistencia de datos.")
            
    except Exception as e:
        logger.error(f"Fallo crítico en la ejecución del proceso: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    ejecutar_pipeline()
