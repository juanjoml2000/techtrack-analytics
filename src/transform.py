import logging
import pandas as pd
import requests
import os
from typing import List, Dict, Any
from supabase import Client

logger = logging.getLogger("transform")

def notificar_descuento_n8n(producto: Dict[str, Any], descuento: float) -> None:
    """
    Sincroniza con el servicio de alertas externas para notificar caídas de precios significativas.
    """
    n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL")
    if not n8n_webhook_url:
        logger.debug("N8N_WEBHOOK_URL no configurada. Omitiendo notificación externa.")
        return
        
    payload = {
        "producto_id": producto["producto_id"],
        "nombre": producto["nombre"],
        "precio_actual": producto["precio_actual"],
        "descuento_porcentaje": round(descuento, 2),
        "url_producto": producto["url_producto"],
        "mensaje": (
            f"🚨 ¡OFERTA DETECTADA! 🚨\n\n"
            f"El producto *{producto['nombre']}* ha registrado una bajada del {descuento:.1f}% "
            f"con respecto a su media histórica.\n\n"
            f"💵 Precio Actual: {producto['precio_actual']:.2f} €\n"
            f"🔗 Enlace: {producto['url_producto']}"
        )
    }
    
    try:
        logger.info(f"Enviando notificación de descuento para {producto['producto_id']}...")
        r = requests.post(n8n_webhook_url, json=payload, timeout=10)
        r.raise_for_status()
        logger.info("Notificación enviada correctamente.")
    except Exception as e:
        logger.error(f"Fallo al registrar la notificación externa: {e}")

def transformar_y_analizar(
    datos_crudos: List[Dict[str, Any]],
    supabase_client: Client
) -> List[Dict[str, Any]]:
    """
    Procesa y limpia los datos recolectados, analiza las medias históricas de precios
    y determina si existen variaciones significativas para alertar de forma oportuna.
    
    Args:
        datos_crudos (List[Dict[str, Any]]): Estructuras de datos crudas recolectadas.
        supabase_client (Client): Cliente del backend de datos.
        
    Returns:
        List[Dict[str, Any]]: Listado de registros normalizados listos para su persistencia.
    """
    if not datos_crudos:
        logger.info("No se encontraron registros para transformar.")
        return []
        
    # Inicialización de la estructura de datos tabulares para análisis
    df = pd.DataFrame(datos_crudos)
    
    # Normalización y filtrado de datos nulos o inconsistentes
    df["precio_actual"] = pd.to_numeric(df["precio_actual"], errors="coerce")
    df = df.dropna(subset=["precio_actual", "producto_id"])
    
    registros_transformados = []
    
    # Análisis evolutivo de precios por producto
    for _, row in df.iterrows():
        producto_id = row["producto_id"]
        precio_actual = float(row["precio_actual"])
        
        # Recuperación de precios históricos desde el almacenamiento relacional
        try:
            res = supabase_client.table("historico_precios")\
                                 .select("precio")\
                                 .eq("producto_id", producto_id)\
                                 .execute()
            
            precios_anteriores = [float(item["precio"]) for item in res.data] if res.data else []
        except Exception as e:
            logger.warning(f"Error consultando histórico relacional para {producto_id}: {e}")
            precios_anteriores = []
            
        if precios_anteriores:
            # Cálculo de la media histórica aritmética
            precio_historico_medio = sum(precios_anteriores) / len(precios_anteriores)
            
            # Evaluación de la variación de precio
            if precio_actual < precio_historico_medio:
                descuento = ((precio_historico_medio - precio_actual) / precio_historico_medio) * 100
            else:
                descuento = 0.0
                
            logger.info(
                f"Producto {producto_id}: Precio Actual = {precio_actual:.2f} € | "
                f"Media Histórica = {precio_historico_medio:.2f} € | Variación = -{descuento:.1f}%"
            )
            
            # Umbral de notificación establecido en el 10%
            if descuento >= 10.0:
                notificar_descuento_n8n(row.to_dict(), descuento)
        else:
            logger.info(f"Registro inicial de precios para el producto {producto_id}.")
            descuento = 0.0
            
        registros_transformados.append({
            "producto_id": row["producto_id"],
            "nombre": row["nombre"],
            "url_producto": row["url_producto"],
            "precio": precio_actual
        })
        
    return registros_transformados
