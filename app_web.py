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
st.set_page_config(page_title="LAIA v22.0 - Agente Logístico", page_icon="🧠", layout="wide")

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

# BLINDAJE 1: Sin f-string
HEADERS = {"Authorization": "token " + GITHUB_TOKEN, "Cache-Control": "no-cache"}

def obtener_github(archivo):
    # BLINDAJE 2: Sin llaves {}
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
    # BLINDAJE 3: Sin llaves {}
    url = "https://api.github.com/repos/" + GITHUB_USER + "/" + GITHUB_REPO + "/contents/" + archivo
    return requests.put(url, headers=HEADERS, json=payload).status_code in [200, 201]

# ==========================================
# 3. MOTOR MATEMÁTICO (STOCK NUEVO/USADO)
# ==========================================
def calcular_stock_web(df):
    if df.empty: return pd.DataFrame(), pd.DataFrame()
    df_c = df.copy()
    
    # Normalización
    df_c.columns = df_c.columns.str.lower().str.strip()
    df_c['cantidad'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(1)
    
    def procesar_fila(row):
        condicion = str(row.get('condicion', '')).lower()
        tipo = str(row.get('tipo', '')).lower()
        dest = str(row.get('destino', '')).lower()
        cant = row['cantidad']
        
        # Lógica de Stock
        if 'dañ' in condicion or 'obs' in condicion: return 0
        if 'stock' in dest or 'recibido' in tipo: return cant
        if 'enviado' in tipo: return -cant
        return 0

    df_c['val'] = df_c.apply(procesar_fila, axis=1)
    
    # Agrupación por Equipo, Marca y ESTADO (Nuevo/Usado)
    if 'estado_fisico' not in df_c.columns:
        df_c['estado_fisico'] = 'No especificado'

    stock_resumen = df_c.groupby(['equipo', 'marca', 'estado_fisico'])['val'].sum().reset_index()
    stock_resumen = stock_resumen[stock_resumen['val'] > 0]
    
    # Detalle con series
    stock_detalle = df_c[df_c['val'] > 0].copy()
    
    return stock_resumen, stock_detalle

# ==========================================
# 4. PROMPT DE INTELIGENCIA (EL CEREBRO)
# ==========================================
SYSTEM_PROMPT = """
Actúa como un Auditor de Inventario experto llamado LAIA. Tu objetivo es procesar movimientos de bodega.

REGLAS DE CATEGORÍA:
1. EQUIPOS (Requieren SERIE): Laptop, CPU, Monitor, Impresora, Camara, Bocina.
2. PERIFÉRICOS (No requieren serie): Mouse, Teclado, Cables, Cargador.

REGLAS DE NEGOCIO:
- Si el usuario no dice si es NUEVO o USADO, DEBES PREGUNTAR (estado_fisico).
- Si el usuario no dice si está BUENO o DAÑADO, DEBES PREGUNTAR (condicion).
- Ignora info irrelevante (dibujitos, suciedad).
- Captura info de daño (pantalla rota, no prende) y marca condicion="Dañado".
- Si algo es BUENO pero lo mandan a TALLER, pregunta por qué.

ESTRUCTURA DE RESPUESTA JSON:
{
  "status": "READY" o "INCOMPLETE" o "QUESTION",
  "missing_info": "Texto preguntando qué falta",
  "items": [{ "equipo": "...", "marca": "...", "serie": "...", "cantidad": 1, "estado_fisico": "Nuevo/Usado", "condicion": "Bueno/Dañado/Obsoleto", "tipo": "Recibido/Enviado", "destino": "Stock/Agencia/Taller", "reporte": "..." }]
}
"""

# ==========================================
# 5. INTERFAZ STREAMLIT
# ==========================================
st.title("🤖 LAIA v22.0: Agente Inteligente")

if "messages" not in st.session_state: st.session_state.messages = []
if "draft" not in st.session_state: st.session_state.draft = None

tab1, tab2 = st.tabs(["💬 Chat de Gestión", "📊 Dashboard de Stock"])

with tab1:
    # Mostrar historial de chat
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if prompt := st.chat_input("Ej: Llegaron 5 laptops de Pascuales..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        # Llamada a la IA
        try:
            client = genai.Client(api_key=API_KEY)
            # Usamos concatenación simple en lugar de f-string complejo
            contexto = SYSTEM_PROMPT + "\nHistorial reciente: " + str(st.session_state.messages[-3:]) + "\nUsuario dice: " + prompt
            
            response = client.models.generate_content(model="gemini-2.0-flash-exp", contents=contexto)
            
            # Extraer JSON de la respuesta
            raw_text = response.text
            if "```json" in raw_text: 
                raw_text = raw_text.split("```json")[1].split("```")[0]
            elif "```" in raw_text: 
                raw_text = raw_text.split("```")[1].split("```")[0]
            
            res_json = json.loads(raw_text)
            
            if res_json.get("status") == "READY":
                st.session_state.draft = res_json.get("items", [])
                resp_laia = "✅ Tengo la información completa. Revisa la tabla de abajo y confirma el registro."
            else:
                resp_laia = res_json.get("missing_info", "Necesito más detalles.")
                st.session_state.draft = None

            with st.chat_message("assistant"): st.markdown(resp_laia)
            st.session_state.messages.append({"role": "assistant", "content": resp_laia})

        except Exception as e:
            # BLINDAJE FINAL: Aquí estaba el error. Lo cambiamos por suma de texto.
            st.error("Error procesando respuesta: " + str(e))

    # Zona de Confirmación (Si hay un borrador listo)
    if st.session_state.draft:
        st.write("### 📋 Pre-visualización de Registro")
        df_draft = pd.DataFrame(st.session_state.draft)
        st.table(df_draft)
        
        c1, c2 = st.columns(2)
        if c1.button("✅ CONFIRMAR Y GUARDAR"):
            with st.spinner("Guardando en GitHub..."):
                for item in st.session_state.draft:
                    item["fecha"] = (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                
                # Enviar al buzón
                if enviar_github(FILE_BUZON, st.session_state.draft):
                    st.success("¡Registro guardado exitosamente!")
                    st.session_state.draft = None
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
        st_resumen, st_detalle = calcular_stock_web(df_hist)
        
        # KPIs
        k1, k2, k3 = st.columns(3)
        if not st_resumen.empty:
            k1.metric("📦 Total Items", int(st_resumen['val'].sum()))
        else:
            k1.metric("📦 Total Items", 0)
            
        k2.metric("⚠️ Dañados", len(df_hist[df_hist['condicion'].astype(str).str.lower().str.contains('dañ', na=False)]))
        k3.metric("🚚 Movimientos", len(df_hist))

        t_res, t_det, t_dañ = st.tabs(["📦 Resumen de Stock", "🔍 Detalle por Series", "🚨 Dañados/Obsoletos"])
        
        with t_res:
            st.write("### Resumen Minimalista (Opción B)")
            if not st_resumen.empty:
                # Pivotar para ver: Equipo | Marca | Nuevo | Usado
                try:
                    res_pivot = st_resumen.pivot_table(index=['equipo', 'marca'], 
                                                     columns='estado_fisico', 
                                                     values='val', 
                                                     aggfunc='sum').fillna(0)
                    st.dataframe(res_pivot, use_container_width=True)
                except:
                    st.dataframe(st_resumen, use_container_width=True)
            else: st.info("No hay stock disponible.")

        with t_det:
            st.write("### Inventario Detallado (Series)")
            if not st_detalle.empty:
                cols_to_show = ['fecha', 'equipo', 'marca', 'serie', 'estado_fisico', 'destino']
                cols_existentes = [c for c in cols_to_show if c in st_detalle.columns]
                st.dataframe(st_detalle[cols_existentes], use_container_width=True, hide_index=True)

        with t_dañ:
            df_bad = df_hist[df_hist['condicion'].astype(str).str.lower().str.contains('dañ|obs', na=False)]
            if not df_bad.empty:
                st.error("Equipos fuera de servicio")
                st.dataframe(df_bad, use_container_width=True)
            else: st.success("No hay equipos dañados reportados.")
    else:
        st.warning("No se encontraron datos en el histórico.")

# ==========================================
# 6. LIMPIEZA DE CHAT
# ==========================================
if st.sidebar.button("🧹 Borrar Chat"):
    st.session_state.messages = []
    st.session_state.draft = None
    st.rerun()
