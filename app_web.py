import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA (ESTÉTICA MAMADA) ---
st.set_page_config(page_title="LAIA NEURAL SYSTEM", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2e7d32; color: white; border: none; }
    .stTextArea>div>div>textarea { background-color: #1a1c23; color: #00ff00; font-family: 'Courier New', monospace; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
</style>
""", unsafe_allow_html=True)

# --- CREDENCIALES ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Configura los Secrets (GITHUB_TOKEN y GOOGLE_API_KEY).")
    st.stop()

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"

# CORREGIDO: Se agregó la variable {GITHUB_TOKEN} dentro de las llaves
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Cache-Control": "no-cache"}

# --- FUNCIONES DE APOYO (ESTRUCTURA ORIGINAL EXPANDIDA) ---
def obtener_fecha_ecuador():
    return (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")

def obtener_github(archivo):
    # CORREGIDO: Se agregaron las variables a la URL
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}"
    try:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 200:
            d = resp.json()
            return json.loads(base64.b64decode(d['content']).decode('utf-8')), d['sha']
    except Exception as e:
        pass
    return [], None

def enviar_buzon(datos):
    if not isinstance(datos, list): datos = [datos]
    actuales, sha = obtener_github(FILE_BUZON)
    actuales.extend(datos)
    payload = {
        "message": "LAIA NEURAL UPDATE",
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha
    }
    # CORREGIDO: Se agregaron las variables a la URL
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_BUZON}"
    return requests.put(url, headers=HEADERS, json=payload).status_code in [200, 201]

def extraer_json(texto):
    try:
        if "```" in texto:
            texto = texto.split("```")[1]
            if texto.startswith("json"): texto = texto[4:]
        inicio = texto.find("[")
        if inicio == -1: inicio = texto.find("{")
        fin = texto.rfind("]") + 1
        if fin == 0: fin = texto.rfind("}") + 1
        if inicio != -1 and fin > inicio:
            return texto[inicio:fin].strip()
        return texto.strip()
    except: return ""

# --- INTERFAZ ---
st.title("🤖 LAIA NEURAL ENGINE v9.0")
t1, t2, t3, t4 = st.tabs(["📝 Registro Inteligente", "💬 Chat Consultor", "🗑️ Limpieza Quirúrgica", "📊 BI & Historial"])

# --- TAB 1: REGISTRO & ESTRATEGIA (IA MEJORADA V9.3) ---
with t1:
    st.subheader("📝 Gestión de Movimientos")
    st.info("💡 IA V9.3: Detecta Daños Críticos vs Estéticos. Si pides 'Informe Técnico', lo etiqueta automáticamente.")
    texto_input = st.text_area("Orden Logística:", height=200, placeholder="Ej: Recibí Laptop HP con pantalla rota, hacer informe técnico. O llegaron 50 mouses a stock...")
    
    if st.button("🚀 EJECUTAR ACCIÓN INTELIGENTE", type="primary"):
        if texto_input.strip():
            with st.spinner("LAIA diagnosticando estado y procesando inventario..."):
                try:
                    client = genai.Client(api_key=API_KEY)
                    
                    # --- PROMPT MAESTRO DE DIAGNÓSTICO ---
                    prompt = f"""
                    Actúa como un Auditor de Inventario y Técnico de Soporte Nivel 2.
                    TEXTO ORIGINAL: "{texto_input}"
                    
                    TU MISIÓN (SIGUE ESTOS PASOS ESTRICTAMENTE):

                    1. **CORRECCIÓN ORTOGRÁFICA**: 
                       - Corrige errores (ej: "cragador"->"Cargador", "mause"->"Mouse", "laptp"->"Laptop").

                    2. **DIAGNÓSTICO DE ESTADO (CRÍTICO)**:
                       - **DAÑADO**: Si menciona fallas funcionales (ej: "Pantalla rota", "No prende", "No da video", "Teclado no sirve", "Golpeado fuerte").
                         -> El campo 'estado' DEBE SER "Dañado".
                       - **USADO**: Si solo son defectos cosméticos (ej: "Rayones", "Despintado", "Sucio", "Gomas gastadas").
                         -> El campo 'estado' DEBE SER "Usado".

                    3. **SOLICITUD DE INFORME TÉCNICO (IT)**:
                       - Si el usuario pide "Hacer informe", "Revisar", "Diagnosticar" o "IT":
                         -> AGREGA la etiqueta "[REQUIERE IT]" al principio del campo 'reporte'.

                    4. **LÓGICA DE STOCK Y ACCESORIOS**:
                       - Si dice "a stock", "bodega" o son consumibles masivos (50 mouses) -> Destino: "Stock", Cantidad: Total.
                       - Equipos con serie (Laptop, CPU) -> Cantidad: 1 (una fila por equipo).
                       - **Accesorio Adjunto** ("Laptop con cargador") -> NO crees fila extra. Ponlo en 'reporte' de la Laptop.
                       - **Accesorio Suelto** ("50 cargadores a stock") -> SÍ crea fila.

                    FORMATO DE SALIDA (JSON ARRAY):
                    Ejemplo Dañado:
                    [{{ "destino": "Taller", "tipo": "Recibido", "cantidad": 1, "equipo": "Laptop", "marca": "Dell", "serie": "ABC", "estado": "Dañado", "ubicacion": "Mesa 1", "reporte": "[REQUIERE IT] Pantalla trizada y bisagra rota. Incluye cargador." }}]
                    """
                    
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                    json_limpio = extraer_json(resp.text)
                    
                    if json_limpio:
                        datos = json.loads(json_limpio)
                        fecha = obtener_fecha_ecuador()
                        for d in datos: d["fecha"] = fecha
                        
                        if enviar_buzon(datos):
                            st.success(f"✅ LAIA procesó {len(datos)} registros.")
                            if any(d.get('estado') == 'Dañado' for d in datos):
                                st.warning("⚠️ Se detectaron equipos DAÑADOS. Se moverán a la hoja de reportes.")
                            st.table(pd.DataFrame(datos))
                        else:
                            st.error("Error de conexión con GitHub.")
                    else:
                        st.warning("La IA no pudo interpretar la orden. Intenta ser más específico.")
                            
                except Exception as e:
                    st.error(f"Error crítico en IA: {e}")

# --- TAB 2: CHAT IA (CON CONTEXTO DE INVENTARIO) ---
with t2:
    st.subheader("💬 Consulta Inteligente")
    if "messages" not in st.session_state: st.session_state.messages = []
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p_chat := st.chat_input("¿Qué equipos tenemos en Ambato?"):
        st.session_state.messages.append({"role": "user", "content": p_chat})
        with st.chat_message("user"): st.markdown(p_chat)
        
        # Inyectamos el historial completo para que la IA responda con la verdad
        hist, _ = obtener_github(FILE_HISTORICO)
        # Convertir a string seguro para el prompt
        hist_str = json.dumps(hist[-150:]) if hist else "[]"
        contexto = f"INVENTARIO ACTUAL: {hist_str}. Responde basado solo en estos datos."
        
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=contexto + p_chat)
        
        with st.chat_message("assistant"): st.markdown(resp.text)
        st.session_state.messages.append({"role": "assistant", "content": resp.text})

# --- TAB 3: LIMPIEZA QUIRÚRGICA (LA MAGIA QUE PEDISTE) ---
with t3:
    st.subheader("🗑️ Eliminación por Razonamiento")
    st.warning("⚠️ Aquí puedes ser descriptivo: 'Borra el CPU de Ambato' o 'Borra los mouses dañados'")
    txt_borrar = st.text_input("¿Qué quieres eliminar?")
    
    if st.button("🔥 EJECUTAR BORRADO DE PRECISIÓN"):
        if txt_borrar:
            with st.spinner("LAIA localizando el registro en el historial..."):
                # PASO 1: Obtener historial para que la IA identifique el registro
                hist, _ = obtener_github(FILE_HISTORICO)
                contexto_borrado = json.dumps(hist[-100:]) if hist else "[]"
                
                client = genai.Client(api_key=API_KEY)
                # CORREGIDO: Se insertó {txt_borrar} en el prompt
                prompt_b = f"""
                DADOS ESTOS REGISTROS: {contexto_borrado}
                ORDEN DEL USUARIO: "{txt_borrar}"
                TAREA: Identifica qué registro exacto quiere borrar. 
                Responde UNICAMENTE un JSON con este formato:
                [{{"accion": "borrar_quirurgico", "serie": "SERIE_A_BORRAR", "equipo": "NOMBRE", "motivo": "RAZON"}}]
                Si el usuario dice "borra todo", la accion es "borrar_todo".
                """
                resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_b)
                orden_json = extraer_json(resp.text)
                
                if orden_json:
                    try:
                        data_borrado = json.loads(orden_json)
                        if enviar_buzon(data_borrado):
                            st.success("🎯 LAIA identificó el registro y envió la orden de eliminación.")
                            st.json(orden_json)
                    except Exception as e:
                        st.error(f"Error procesando respuesta de borrado: {e}")
                else:
                    st.error("LAIA no pudo identificar qué registro borrar.")

# --- TAB 4: BI & HISTORIAL (DASHBOARD INTELIGENTE V2.0) ---
with t4:
    # 1. Cabecera y Botón de Recarga
    c_head1, c_head2 = st.columns([3, 1])
    c_head1.subheader("📊 Dashboard de Control de Activos")
    if c_head2.button("🔄 Actualizar Datos en Tiempo Real"):
        st.rerun()

    datos, _ = obtener_github(FILE_HISTORICO)
    
    if datos:
        df = pd.DataFrame(datos)
        
        # --- PRE-PROCESAMIENTO INTELIGENTE ---
        # Aseguramos columnas clave
        for col in ['destino', 'estado', 'marca', 'equipo', 'tipo']:
            if col not in df.columns: df[col] = "N/A"
            
        # Filtros Automáticos
        df_stock = df[df['destino'].str.lower() == 'stock'].copy()
        df_mov = df[df['destino'].str.lower() != 'stock'].copy()
        df_bad = df[df['estado'].str.lower() == 'dañado'].copy()
        
        # --- METRICAS KPI (Key Performance Indicators) ---
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("📦 Total Activos", len(df), delta="Inventario Global")
        kpi2.metric("✅ En Stock", len(df_stock), delta="Disponibles", delta_color="normal")
        kpi3.metric("🚚 Movimientos", len(df_mov), delta="Enviados/Recibidos", delta_color="off")
        kpi4.metric("⚠️ Equipos Dañados", len(df_bad), delta="Atención Requerida", delta_color="inverse")
        
        st.divider()

        # --- SUB-PESTAÑAS DE CLASIFICACIÓN ---
        st_t1, st_t2, st_t3, st_t4 = st.tabs(["📂 Maestro General", "📦 Bodega (Stock)", "🚚 Tráfico (Enviados/Recibidos)", "⚠️ HOSPITAL (Dañados)"])
        
        # 1. MAESTRO GENERAL + GRÁFICOS
        with st_t1:
            st.markdown("### 📈 Tendencias de Inventario")
            col_g1, col_g2 = st.columns(2)
            
            # Gráfico 1: Top Marcas
            if 'marca' in df.columns:
                conteo_marca = df['marca'].value_counts().head(5)
                col_g1.bar_chart(conteo_marca, color="#2e7d32")
                col_g1.caption("Top 5 Marcas en Inventario")
            
            # Gráfico 2: Distribución por Estado
            if 'estado' in df.columns:
                conteo_estado = df['estado'].value_counts()
                col_g2.bar_chart(conteo_estado, color="#1F4E78")
                col_g2.caption("Estado de Salud de los Equipos")

            st.dataframe(df, use_container_width=True, hide_index=True)

        # 2. VISTA DE STOCK (Agrupado)
        with st_t2:
            st.info("Vista filtrada: Solo equipos disponibles en Bodega/Stock.")
            if not df_stock.empty:
                # Mostramos tabla normal
                st.dataframe(
                    df_stock, 
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "cantidad": st.column_config.NumberColumn("Cant", format="%d"),
                        "estado": st.column_config.TextColumn("Condición")
                    }
                )
                # Resumen rápido por tipo
                st.caption("Resumen Rápido de Stock:")
                st.json(df_stock['equipo'].value_counts().to_dict())
            else:
                st.warning("Bodega vacía. No hay stock registrado.")

        # 3. VISTA DE MOVIMIENTOS
        with st_t3:
            st.markdown("### 🚦 Historial de Envíos y Recepciones")
            # Filtros interactivos
            filtro_tipo = st.radio("Filtrar por:", ["Todos", "Enviados", "Recibidos"], horizontal=True)
            
            df_show = df_mov
            if filtro_tipo == "Enviados":
                df_show = df_mov[df_mov['tipo'].astype(str).str.lower().str.contains('enviado')]
            elif filtro_tipo == "Recibidos":
                df_show = df_mov[df_mov['tipo'].astype(str).str.lower().str.contains('recibido')]
            
            st.dataframe(df_show, use_container_width=True, hide_index=True)

        # 4. VISTA DE DAÑADOS (La IA detecta esto)
        with st_t4:
            st.error("🚨 ZONA ROJA: Equipos que requieren reparación o baja.")
            if not df_bad.empty:
                # Reordenar columnas para ver el reporte primero
                cols = list(df_bad.columns)
                if 'reporte' in cols:
                    cols.insert(0, cols.pop(cols.index('reporte')))
                
                st.data_editor(
                    df_bad[cols], 
                    use_container_width=True, 
                    hide_index=True, 
                    disabled=True
                )
            else:
                st.success("¡Excelente! No hay equipos reportados como dañados.")

        # --- BOTÓN DE DESCARGA GLOBAL ---
        st.divider()
        col_d1, col_d2 = st.columns([3,1])
        with col_d2:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Excel Completo (.csv)",
                data=csv,
                file_name=f"Inventario_Jaher_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                type="primary"
            )
            
    else:
        st.warning("⚠️ No se pudo conectar con el Histórico. Verifica tu internet o el Token.")
