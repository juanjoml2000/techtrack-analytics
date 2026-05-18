-- Habilitar extensiones necesarias si hicieran falta
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Tabla de Productos (dimensión de productos)
CREATE TABLE IF NOT EXISTS productos (
    producto_id VARCHAR(50) PRIMARY KEY,
    nombre TEXT NOT NULL,
    url_producto TEXT,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 2. Tabla de Histórico de Precios (hechos de precios extraídos en el tiempo)
CREATE TABLE IF NOT EXISTS historico_precios (
    id BIGSERIAL PRIMARY KEY,
    producto_id VARCHAR(50) REFERENCES productos(producto_id) ON DELETE CASCADE,
    precio NUMERIC(12, 2) NOT NULL,
    fecha_extraccion TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 3. Índices para optimización de consultas en el Dashboard
CREATE INDEX IF NOT EXISTS idx_historico_producto_id ON historico_precios(producto_id);
CREATE INDEX IF NOT EXISTS idx_historico_fecha_extraccion ON historico_precios(fecha_extraccion);

-- 4. Comentarios para autodocumentación de la base de datos
COMMENT ON TABLE productos IS 'Catálogo unificado de productos tecnológicos.';
COMMENT ON TABLE historico_precios IS 'Registro cronológico del histórico de precios de los productos.';

