# TechTrack Analytics 📊

[![ETL Pipeline](https://github.com/tu-usuario/techtrack-analytics/actions/workflows/sincronizacion_cron.yml/badge.svg)](https://github.com/tu-usuario/techtrack-analytics/actions/workflows/sincronizacion_cron.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B.svg)](https://streamlit.io)
[![Supabase](https://img.shields.io/badge/Supabase-Database-3ECF8E.svg)](https://supabase.com)

**TechTrack Analytics** es una arquitectura de datos end-to-end diseñada para la extracción, estructuración, análisis histórico y visualización interactiva de precios de hardware tecnológico. El objetivo del sistema es dotar de inteligencia de negocio (BI) para la detección de anomalías y ventanas óptimas de compra mediante el cálculo de desviaciones sobre medias históricas.

---

## 🏗️ Arquitectura del Sistema

El proyecto se estructura en un pipeline ETL (Extract, Transform, Load) modular:

1.  **Extracción (Extract):** Automatización de recolección de datos mediante solicitudes HTTP estructuradas (`requests` y `BeautifulSoup4`). Implementa resolución criptográfica de firmas de sesión (SHA-256) para garantizar el acceso consistente a los endpoints.
2.  **Procesamiento (Transform):** Limpieza, normalización y cálculo de métricas financieras usando `pandas`. Incluye integración de webhooks hacia plataformas de mensajería (n8n, Telegram, Slack) para alertas en tiempo real ante caídas de precio superiores al umbral definido.
3.  **Persistencia (Load):** Almacenamiento relacional normalizado en **PostgreSQL (Supabase)**. Se emplea un modelo estrella dimensional con separación entre el catálogo único (dimensión) y las muestras temporales de precio (hechos).
4.  **Visualización (Dashboard):** Cuadro de mando interactivo desarrollado nativamente con `Streamlit` y `Plotly`. Permite el análisis visual de series temporales y comparativas de mercado en formato Euro (€).

---

## 🚀 Despliegue y Ejecución Local

El proyecto está completamente contenerizado mediante Docker para garantizar reproducibilidad en cualquier entorno.

### Requisitos Previos

*   [Docker](https://docs.docker.com/get-docker/) y Docker Compose instalados.
*   Una cuenta y proyecto activo en [Supabase](https://supabase.com/).
*   *(Opcional)* URL de un webhook para alertas (ej. n8n).

### Configuración

1.  Clona este repositorio:
    ```bash
    git clone https://github.com/tu-usuario/techtrack-analytics.git
    cd techtrack-analytics
    ```
2.  Copia el archivo de configuración de entorno de ejemplo:
    ```bash
    cp .env.example .env
    ```
3.  Completa el archivo `.env` con tus credenciales de Supabase:
    ```env
    SUPABASE_URL=https://tu-id-proyecto.supabase.co
    SUPABASE_KEY=tu-api-key-secreta
    N8N_WEBHOOK_URL=https://tu-webhook-n8n.com/webhook/alerta # Opcional
    ```

### Ejecución

El ecosistema se divide en dos contenedores principales:

1.  **Ejecutar el Pipeline ETL (Extracción y Carga):**
    Este comando lanza un contenedor temporal que realiza la sincronización de datos y finaliza inmediatamente.
    ```bash
    docker compose run --rm etl
    ```

2.  **Levantar el Panel de Visualización (Dashboard):**
    Este servicio corre en segundo plano y despliega la interfaz gráfica.
    ```bash
    docker compose up -d dashboard
    ```
    Accede al dashboard en tu navegador a través de: [http://localhost:8501](http://localhost:8501)

---

## ⏱️ Automatización Continua (CI/CD)

El repositorio incluye un flujo de trabajo de **GitHub Actions** (`.github/workflows/sincronizacion_cron.yml`) configurado para ejecutar el pipeline ETL automáticamente todos los días a las 02:00 AM UTC.

Para activarlo en tu fork, asegúrate de configurar los siguientes secretos en **Settings > Secrets and variables > Actions**:
*   `SUPABASE_URL`
*   `SUPABASE_KEY`
*   `N8N_WEBHOOK_URL` (opcional)

---

## 🗄️ Esquema de Base de Datos

El diseño físico de la base de datos se encuentra detallado en `src/schema.sql`.

*   **Tabla `productos`:** Catálogo maestro unificado.
*   **Tabla `historico_precios`:** Registro cronológico de muestras financieras.

> *Nota: Asegúrese de aplicar este esquema DDL en su instancia de PostgreSQL antes de la primera ejecución del pipeline.*
