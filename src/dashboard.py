import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

st.set_page_config(
    page_title="Monitor de Precios - Hardware",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Solo unos ajustes mínimos, nada de CSS masivo
st.markdown("""<style>
    .block-container { padding-top: 2rem; }
    /* Estilizar métricas sin romper el modo oscuro/claro */
    div[data-testid="stMetric"] { border-left: 3px solid #5B8DEF; padding-left: 15px; }
    /* Ocultar elementos de Streamlit (Deploy, Menú, Footer) */
    .stDeployButton {display:none;}
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer { visibility: hidden; }
</style>""", unsafe_allow_html=True)


# --- Conexión a datos ---

@st.cache_resource
def _supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)

@st.cache_data(ttl=120)
def cargar_datos():
    sb = _supabase()
    if not sb:
        return pd.DataFrame(), pd.DataFrame()
    try:
        prod = pd.DataFrame(sb.table("productos").select("*").execute().data or [])
        hist = pd.DataFrame(
            sb.table("historico_precios").select("*")
            .order("fecha_extraccion", desc=True).execute().data or []
        )
        return prod, hist
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame(), pd.DataFrame()


def fmt_eur(v):
    """Formatea un número como euros: 1.234,56 €"""
    return f"{v:,.2f} €".replace(",", "_").replace(".", ",").replace("_", ".")


# --- Layout principal ---

st.title("🔍 Monitor de Precios")
st.caption("Seguimiento de precios de hardware tecnológico · Datos en tiempo real desde MercadoLibre")

df_prod, df_hist = cargar_datos()

if df_prod.empty or df_hist.empty:
    st.warning("No hay datos todavía. Ejecuta el pipeline ETL para empezar:")
    st.code("docker compose run --rm etl", language="bash")
    st.stop()

# Preparar dataset unificado
df = pd.merge(df_hist, df_prod, on="producto_id", how="inner")
df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
# Convertir a datetime asumiendo UTC y luego cambiar a hora peninsular española
df["fecha_extraccion"] = pd.to_datetime(df["fecha_extraccion"], utc=True).dt.tz_convert('Europe/Madrid')
df = df.sort_values("fecha_extraccion")

# Último precio de cada producto
ultimo = df.groupby("producto_id").last().reset_index()
n_productos = len(ultimo)
n_muestras = len(df)
precio_medio_global = ultimo["precio"].mean()

# --- Sidebar: filtros reales ---
with st.sidebar:
    st.header("Filtros")
    
    # Filtro de rango de precios
    p_min, p_max = float(ultimo["precio"].min()), float(ultimo["precio"].max())
    if p_min < p_max:
        rango = st.slider(
            "Rango de precio (€)", 
            min_value=p_min, max_value=p_max, 
            value=(p_min, p_max),
            format="%.0f €"
        )
    else:
        rango = (p_min, p_max)
    
    # Filtro de productos
    todos_nombres = sorted(ultimo["nombre"].tolist())
    seleccion = st.multiselect(
        "Productos a mostrar",
        options=todos_nombres,
        default=todos_nombres,
        help="Deja vacío para ver todos"
    )
    if not seleccion:
        seleccion = todos_nombres
    
    st.divider()
    if st.button("🔄 Actualizar datos"):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    st.caption(f"Última sincronización: {df['fecha_extraccion'].max().strftime('%d/%m/%Y %H:%M')}")

# Aplicar filtros
mask_prod = ultimo["nombre"].isin(seleccion)
mask_precio = (ultimo["precio"] >= rango[0]) & (ultimo["precio"] <= rango[1])
filtrado = ultimo[mask_prod & mask_precio]
ids_filtrados = filtrado["producto_id"].tolist()
df_filtrado = df[df["producto_id"].isin(ids_filtrados)]


# --- Métricas rápidas (usando st.metric nativo, no HTML custom) ---

col1, col2, col3 = st.columns(3)
col1.metric("Productos monitoreados", n_productos)
col2.metric("Muestras de precio", n_muestras)
col3.metric("Precio medio", fmt_eur(precio_medio_global))

st.divider()

# --- Tabs para organizar el contenido ---

tab_resumen, tab_evolucion, tab_tabla = st.tabs([
    "📊 Resumen general", 
    "📈 Evolución de precios", 
    "📋 Tabla de datos"
])

with tab_resumen:
    if filtrado.empty:
        st.info("No hay productos que coincidan con los filtros seleccionados.")
    else:
        # Gráfico de barras horizontal con los precios actuales
        fig_barras = px.bar(
            filtrado.sort_values("precio", ascending=True),
            x="precio",
            y="nombre",
            orientation="h",
            labels={"precio": "Precio (€)", "nombre": ""},
            color="precio",
            color_continuous_scale="blues",
        )
        fig_barras.update_layout(
            title="Comparativa de precios actuales",
            showlegend=False,
            coloraxis_showscale=False,
            height=max(350, len(filtrado) * 45),
            margin=dict(l=20, r=20, t=50, b=20),
            yaxis=dict(tickfont=dict(size=11)),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig_barras.update_traces(
            texttemplate="%{x:,.0f} €", 
            textposition="outside",
            textfont_size=10,
        )
        st.plotly_chart(fig_barras, use_container_width=True)
        
        # Detectar variaciones significativas
        variaciones = []
        for _, row in filtrado.iterrows():
            precios_prod = df[df["producto_id"] == row["producto_id"]]["precio"].tolist()
            if len(precios_prod) > 1:
                media = sum(precios_prod) / len(precios_prod)
                if row["precio"] < media:
                    var = ((media - row["precio"]) / media) * 100
                    if var >= 5.0:
                        variaciones.append({
                            "Producto": row["nombre"],
                            "Precio actual": fmt_eur(row["precio"]),
                            "Media histórica": fmt_eur(media),
                            "Variación": f"-{var:.1f}%",
                            "url": row["url_producto"]
                        })
        
        if variaciones:
            st.subheader("⚡ Bajadas de precio detectadas")
            st.caption("Productos cuyo precio actual está por debajo de su media histórica (≥5%)")
            for v in variaciones:
                with st.expander(f"**{v['Producto']}** → {v['Variación']}"):
                    c1, c2 = st.columns(2)
                    c1.write(f"**Precio actual:** {v['Precio actual']}")
                    c2.write(f"**Media histórica:** {v['Media histórica']}")
                    st.link_button("Ver en MercadoLibre", v["url"])
        else:
            st.info("No se detectan bajadas significativas respecto a la media histórica.")


with tab_evolucion:
    if df_filtrado.empty:
        st.info("No hay datos de evolución para los filtros seleccionados.")
    else:
        # Selector individual para ver la tendencia
        producto_sel = st.selectbox(
            "Selecciona un producto:",
            options=sorted(df_filtrado["nombre"].unique().tolist())
        )
        
        df_sel = df_filtrado[df_filtrado["nombre"] == producto_sel].copy()
        
        if len(df_sel) < 2:
            st.info(f"Solo hay una muestra para **{producto_sel}**. Necesitas más ejecuciones del ETL para ver la tendencia.")
            # Aun así mostramos el dato
            st.metric("Precio registrado", fmt_eur(df_sel["precio"].iloc[0]))
        else:
            fig_linea = go.Figure()
            fig_linea.add_trace(go.Scatter(
                x=df_sel["fecha_extraccion"],
                y=df_sel["precio"],
                mode="lines+markers",
                name=producto_sel,
                line=dict(color="#5B8DEF", width=2.5),
                marker=dict(size=7),
                hovertemplate="%{x|%d/%m/%Y %H:%M}<br>%{y:,.0f} €<extra></extra>"
            ))
            
            # Línea de media histórica
            media_prod = df_sel["precio"].mean()
            fig_linea.add_hline(
                y=media_prod, 
                line_dash="dash", 
                line_color="#FF6B6B",
                annotation_text=f"Media: {fmt_eur(media_prod)}",
                annotation_position="top right"
            )
            
            fig_linea.update_layout(
                title=f"Evolución de precio — {producto_sel[:60]}",
                xaxis_title="",
                yaxis_title="Precio (€)",
                height=420,
                margin=dict(l=20, r=20, t=50, b=20),
                hovermode="x unified",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_linea, use_container_width=True)
            
            # Estadísticas básicas del producto
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Mínimo registrado", fmt_eur(df_sel["precio"].min()))
            col_b.metric("Máximo registrado", fmt_eur(df_sel["precio"].max()))
            col_c.metric("Nº de muestras", len(df_sel))


with tab_tabla:
    st.subheader("Datos completos del catálogo")
    
    # Preparar tabla exportable
    df_tabla = filtrado[["producto_id", "nombre", "precio", "fecha_extraccion", "url_producto"]].copy()
    df_tabla["precio_fmt"] = df_tabla["precio"].apply(fmt_eur)
    df_tabla["fecha_extraccion"] = df_tabla["fecha_extraccion"].dt.strftime("%d/%m/%Y %H:%M")
    
    # Renombrar para la vista
    df_vista = df_tabla[["producto_id", "nombre", "precio_fmt", "fecha_extraccion"]].rename(columns={
        "producto_id": "ID",
        "nombre": "Producto",
        "precio_fmt": "Último precio",
        "fecha_extraccion": "Fecha extracción"
    })
    
    st.dataframe(df_vista, use_container_width=True, hide_index=True)
    
    # Botón de descarga CSV
    csv = df_tabla[["producto_id", "nombre", "precio", "fecha_extraccion"]].to_csv(index=False, sep=";")
    st.download_button(
        "📥 Descargar CSV",
        data=csv,
        file_name=f"precios_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )
