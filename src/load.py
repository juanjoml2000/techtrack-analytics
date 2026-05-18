import logging
import os
from typing import List, Dict, Any
from supabase import create_client, Client

logger = logging.getLogger("load")

def conectar_backend() -> Client:
    """
    Inicializa el cliente de acceso al backend de datos a partir de las variables de entorno.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        raise ValueError(
            "Variables de configuración de base de datos no encontradas en el entorno. "
            "Verifique el archivo de configuración .env"
        )
        
    return create_client(supabase_url, supabase_key)

def sincronizar_almacenamiento_relacional(
    datos_transformados: List[Dict[str, Any]],
    supabase_client: Client
) -> bool:
    """
    Sincroniza y persiste el listado de productos estructurados en la base de datos.
    Efectúa la persistencia del catálogo (dimensión productos) e inserta
    las correspondientes muestras temporales (historial de precios).
    
    Args:
        datos_transformados (List[Dict[str, Any]]): Estructuras de datos a almacenar.
        supabase_client (Client): Instancia del cliente de base de datos.
        
    Returns:
        bool: Retorna True si la persistencia fue exitosa.
    """
    if not datos_transformados:
        logger.info("No se encontraron registros pendientes de persistencia.")
        return True
        
    try:
        productos_dimension = []
        historico_hechos = []
        vistos = set()
        
        for item in datos_transformados:
            prod_id = item["producto_id"]
            if prod_id not in vistos:
                productos_dimension.append({
                    "producto_id": prod_id,
                    "nombre": item["nombre"],
                    "url_producto": item["url_producto"]
                })
                vistos.add(prod_id)
                
            historico_hechos.append({
                "producto_id": prod_id,
                "precio": item["precio"]
            })
            
        # Sincronización de registros de catálogo único (Productos)
        logger.info(f"Sincronizando {len(productos_dimension)} elementos en el catálogo...")
        res_prod = supabase_client.table("productos").upsert(productos_dimension).execute()
        
        # Inserción de las muestras temporales de precios
        logger.info(f"Registrando {len(historico_hechos)} muestras en el historial...")
        res_hist = supabase_client.table("historico_precios").insert(historico_hechos).execute()
        
        logger.info("Sincronización del almacenamiento relacional finalizada correctamente.")
        return True
        
    except Exception as e:
        logger.error(f"Fallo durante la persistencia en el almacenamiento relacional: {e}")
        return False
