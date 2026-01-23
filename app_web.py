import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd
import time

# ==========================================
# 1. CONFIGURACIÓN Y ESTILOS
# ==========================================
st.set_page_config(page_title="LAIA v23.0 - Super Agente", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #1E4E78; color: white; border: none; }
    .stChatFloatingInputContainer { background-color: #0e1117; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CREDENCIALES Y GITHUB
# ==========================================
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

# BLINDAJE: Sin f-string para evitar errores de sintaxis
HEADERS = {"Authorization": "token " + GITHUB_TOKEN, "Cache-Control": "no-cache"}

def obtener_github(archivo):
    url = "https://api.github.com/repos/" + GITHUB_USER + "/" + GITHUB_REPO + "/contents/" + archivo
    try:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 200:
            d = resp.json()
            return json.loads(base64.b64decode(d['content']).decode('utf-8')), d['sha']
    except: pass
    return [], None

def enviar_github(archivo, datos, mensaje="Update"):
    actuales, sha = obtener_github(archivo)
    if isinstance(datos, list):
        actuales.extend(datos)
    else:
        actuales.append(datos)
        
    payload = {
        "message": mensaje,
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha
    }
    url = "https://api.github.com/repos/" + GITHUB_USER + "/" + GITHUB_REPO + "/contents/" + archivo
    return requests.put(url, headers=HEADERS, json=payload).status_code in [200, 201]

# ==========================================
# 3. MOTOR MATEMÁTICO
# ==========================================
def calcular_stock_web(df):
    if df.empty: return pd.DataFrame(), pd.DataFrame()
    df_c = df.copy()
    
    df_c.columns = df_c.columns.str.lower().str.strip()
    df_c['cantidad'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(1)
    
    columnas_necesarias = ['condicion', 'estado_fisico', 'tipo', 'destino', 'equipo', 'marca']
    for col in columnas_necesarias:
        if col not in df_c.columns:
            df_c[col] = "No especificado"

    def procesar_fila(row):
        condicion = str(row.get('condicion', '')).lower()
        tipo = str(row.get('tipo', '')).lower()
        dest = str(row.get('destino', '')).lower()
        cant = row['cantidad']
        
        if 'dañ' in condicion or 'obs' in condicion: return 0
        if 'stock' in dest or 'recibido' in tipo: return cant
        if 'enviado' in tipo: return -cant
        return 0

    df_c['val'] = df_c.apply(procesar_fila, axis=1)
    
    stock_resumen = df_c.groupby(['equipo', 'marca', 'estado_fisico'])['val'].sum().reset_index()
    stock_resumen = stock_resumen[stock_resumen['val'] > 0]
    stock_detalle = df_c[df_c['val'] > 0].copy()
    
    return stock_resumen, stock_detalle

# ==========================================
# 4. CEREBRO MEJORADO (SYSTEM PROMPT V2)
# ==========================================
SYSTEM_PROMPT = """
Eres LAIA, una experta en logística y auditoría. 
Tu prioridad absoluta es la PRECISIÓN en los números de serie.

REGLAS CRÍTICAS DE SERIES:
1. SIEMPRE compara la 'cantidad' con el número de 'series' proporcionadas.
2. REGLA DE ORO: 1 Equipo = 1 Serie única. 
   - Si el usuario dice "3 laptops" pero solo da una serie ("123"), NO registres las 3 con la misma serie.
   - En ese caso, debes cambiar el status a "QUESTION" y decir: "He recibido la serie de la primera laptop, pero me faltan las series de las otras 2. Por favor, proporciónalas."
3. NO avances al status "READY" hasta que el número de series coincida EXACTAMENTE con la cantidad de equipos.
4. Si el usuario da una lista de series (ej: 101, 102, 103), crea un objeto individual en el JSON para cada serie.

INSTRUCCIONES DE MEMORIA:
- Analiza toda la conversación. Si antes dijeron "3 laptops" y ahora dan una serie, descuenta esa y pide las demás.

REGLAS DE CATEGORÍA:
- EQUIPOS (OBLIGATORIO pedir SERIE): Laptop, CPU, Monitor, Impresora, Tablet, Camara, Bocina.
- PERIFÉRICOS (NO piden serie): Mouse, Teclado, Cables, Cargador.

ESTRUCTURA DE RESPUESTA JSON:
Si faltan datos o las series no coinciden con la cantidad:
{ "status": "QUESTION", "missing_info": "Explicación de cuántas series faltan o qué dato falta" }

Si cantidad y series COINCIDEN (ej: 3 laptops y 3 series diferentes):
{
  "status": "READY",
  "items": [
    { "equipo": "Laptop", "serie": "SERIE1", "cantidad": 1, ... },
    { "equipo": "Laptop", "serie": "SERIE2", "cantidad": 1, ... }
  ]
}
"""

# ==========================================
# 5. INTERFAZ STREAMLIT
# ==========================================
st.title("🤖 LAIA v23.0: Cerebro Robusto")

if "messages" not in st.session_state: st.session_state.messages = []
if "draft" not in st.session_state: st.session_state.draft = None

tab1, tab2 = st.tabs(["💬 Chat de Gestión", "📊 Dashboard de Stock"])

with tab1:
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if prompt := st.chat_input("Ej: Llegaron 5 laptops de Pascuales..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        try:
            client = genai.Client(api_key=API_KEY)
            
            # TRUCO DE MEMORIA: Convertimos TODO el historial a texto
            historial_txt = ""
            for msg in st.session_state.messages:
                historial_txt += msg["role"].upper() + ": " + msg["content"] + "\n"

            # Concatenación simple (Blindaje anti-errores)
            contexto = SYSTEM_PROMPT + "\n\n--- HISTORIAL DE CONVERSACIÓN ---\n" + historial_txt + "\n\n--- INSTRUCCIÓN ---\nAnaliza el historial completo y decide si falta información."
            
            response = client.models.generate_content(model="gemini-2.0-flash-exp", contents=contexto)
            
            raw_text = response.text
            if "```json" in raw_text: 
                raw_text = raw_text.split("```json")[1].split("```")[0]
            elif "```" in raw_text: 
                raw_text = raw_text.split("```")[1].split("```")[0]
            
            res_json = json.loads(raw_text)
            
            if res_json.get("status") == "READY":
                st.session_state.draft = res_json.get("items", [])
                resp_laia = "✅ ¡Perfecto! Tengo todos los datos (Series, Estados, Cantidades). Revisa la tabla y CONFIRMA."
            else:
                resp_laia = res_json.get("missing_info", "Dame más detalles, por favor.")
                st.session_state.draft = None

            with st.chat_message("assistant"): st.markdown(resp_laia)
            st.session_state.messages.append({"role": "assistant", "content": resp_laia})

        except Exception as e:
            st.error("Error procesando respuesta: " + str(e))

    if st.session_state.draft:
        st.write("### 📋 Pre-visualización de Registro")
        df_draft = pd.DataFrame(st.session_state.draft)
        st.table(df_draft)
        
        c1, c2 = st.columns(2)
        if c1.button("✅ CONFIRMAR Y GUARDAR"):
            with st.spinner("Guardando en GitHub..."):
                for item in st.session_state.draft:
                    item["fecha"] = (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                
                if enviar_github(FILE_BUZON, st.session_state.draft):
                    st.success("¡Registro guardado exitosamente!")
                    st.session_state.draft = None
                    # Limpiamos chat para empezar proceso nuevo limpio
                    st.session_state.messages = [] 
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("Error al conectar con GitHub.")
        
        if c2.button("❌ CANCELAR"):
            st.session_state.draft = None
            st.rerun()

with tab2:
    c_h1, c_h2 = st.columns([3,1])
    c_h1.subheader("📊 Control de Activos y Periféricos")
    if c_h2.button("🔄 Refrescar"): st.rerun()

    hist, _ = obtener_github(FILE_HISTORICO)
    if hist:
        df_hist = pd.DataFrame(hist)
        
        # Parche de compatibilidad
        df_hist.columns = df_hist.columns.str.lower().str.strip()
        columnas_necesarias = ['condicion', 'estado_fisico', 'tipo', 'destino', 'equipo', 'marca']
        for col in columnas_necesarias:
            if col not in df_hist.columns: df_hist[col] = "No especificado"

        st_resumen, st_detalle = calcular_stock_web(df_hist)
        
        k1, k2, k3 = st.columns(3)
        total = int(st_resumen['val'].sum()) if not st_resumen.empty else 0
        k1.metric("📦 Total Items", total)
        k2.metric("⚠️ Dañados", len(df_hist[df_hist['condicion'].astype(str).str.lower().str.contains('dañ', na=False)]))
        k3.metric("🚚 Movimientos", len(df_hist))

        t_res, t_det, t_dañ = st.tabs(["📦 Resumen", "🔍 Series", "🚨 Dañados"])
        
        with t_res:
            st.write("### Resumen Minimalista")
            if not st_resumen.empty:
                try:
                    res_pivot = st_resumen.pivot_table(index=['equipo', 'marca'], 
                                                     columns='estado_fisico', 
                                                     values='val', 
                                                     aggfunc='sum').fillna(0)
                    st.dataframe(res_pivot, use_container_width=True)
                except:
                    st.dataframe(st_resumen, use_container_width=True)
            else: st.info("Bodega Vacía.")

        with t_det:
            if not st_detalle.empty:
                cols = ['fecha', 'equipo', 'marca', 'serie', 'estado_fisico', 'destino']
                existen = [c for c in cols if c in st_detalle.columns]
                st.dataframe(st_detalle[existen], use_container_width=True, hide_index=True)

        with t_dañ:
            df_bad = df_hist[df_hist['condicion'].astype(str).str.lower().str.contains('dañ|obs', na=False)]
            if not df_bad.empty: st.dataframe(df_bad, use_container_width=True)
            else: st.success("Todo en orden.")
    else:
        st.warning("Sin datos.")

if st.sidebar.button("🧹 Borrar Chat"):
    st.session_state.messages = []
    st.session_state.draft = None
    st.rerun()
