import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd
import time

# =========================================
# 1. CONFIGURACIÓN
# ==========================================
st.set_page_config(page_title="LAIA v25.0 - Auditora Conectada", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2e7d32; color: white; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CREDENCIALES
# ==========================================
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Configura los Secrets en Streamlit.")
    st.stop()

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"

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

def enviar_github(archivo, datos, mensaje="LAIA Input"):
    actuales, sha = obtener_github(archivo)
    if isinstance(datos, list): actuales.extend(datos)
    else: actuales.append(datos)
    payload = {
        "message": mensaje,
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha
    }
    url = "https://api.github.com/repos/" + GITHUB_USER + "/" + GITHUB_REPO + "/contents/" + archivo
    return requests.put(url, headers=HEADERS, json=payload).status_code in [200, 201]

# ==========================================
# 3. MOTOR DE STOCK (ALINEADO CON SINCRONIZADOR)
# ==========================================
def calcular_stock_web(df):
    if df.empty: return pd.DataFrame(), pd.DataFrame()
    df_c = df.copy()
    df_c.columns = df_c.columns.str.lower().str.strip()
    
    # Asegurar columnas para el cálculo
    cols = ['estado', 'estado_fisico', 'tipo', 'destino', 'equipo', 'marca', 'cantidad']
    for col in cols:
        if col not in df_c.columns: df_c[col] = "No especificado"
    
    df_c['cant_n'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(1)

    def procesar_fila(row):
        # USAMOS 'estado' que es lo que tu script sincronizador usa
        est = str(row.get('estado', '')).lower() 
        tipo = str(row.get('tipo', '')).lower()
        dest = str(row.get('destino', '')).lower()
        cant = row['cant_n']
        
        if 'dañ' in est or 'obs' in est: return 0
        if dest == 'stock' or 'recibido' in tipo: return cant
        if 'enviado' in tipo: return -cant
        return 0

    df_c['val'] = df_c.apply(procesar_fila, axis=1)
    resumen = df_c.groupby(['equipo', 'marca', 'estado_fisico'])['val'].sum().reset_index()
    resumen = resumen[resumen['val'] > 0]
    return resumen, df_c[df_c['val'] != 0]

# ==========================================
# 4. CEREBRO DE LAIA (CONSTRUCTOR DE JSON PARA SINCRONIZADOR)
# ==========================================
SYSTEM_PROMPT = """
Eres LAIA, la Auditora Jefa de Inventarios de Jaher. Tu inteligencia es superior, proactiva y obsesiva con la completitud de los datos. No eres un chatbot de charla, eres un sistema de control de calidad.

1. REGLA DE VERIFICACIÓN OBLIGATORIA (PENSAMIENTO INTERNO):
Antes de responder, debes marcar en tu "mente" si tienes estos 8 datos:
   1. Equipo | 2. Marca | 3. Serie | 4. Cantidad | 5. Estado (Bueno/Dañado) | 6. Estado Físico (Nuevo/Usado) | 7. Origen/Agencia | 8. Tipo (Recibido/Enviado).
   
   - SI FALTA UNO SOLO: Tu status debe ser "QUESTION".
   - PROHIBIDO EL PING-PONG: Si te faltan 4 datos, PIDE LOS 4 en un solo mensaje numerado. No preguntes uno por uno.

2. CLASIFICACIÓN Y SERIES (SABUESO DE PRECISIÓN):
- EQUIPOS (Serie Obligatoria): Laptop, CPU, Monitor, Impresora, Regulador, UPS, Cámara, Bocina, Tablet.
  * 1 Equipo = 1 Serie Única. Si dicen "2 equipos", necesitas 2 series. 
  * Si el usuario dice "te pasé la serie", búscala en los mensajes de arriba. Si la serie es corta ("123"), ACÉPTALA sin cuestionar.
- PERIFÉRICOS (Bulto): Mouse, Teclado, Cables, Cargador. Control por cantidad.
- COMBOS: Si dicen "Kit" o "CPU con mouse", desglósalo en filas individuales.

3. DEDUCCIÓN LOGÍSTICA (AUDITORÍA INTELIGENTE):
- ORIGEN -> Si dice "Agencia", "Sucursal" o nombre de ciudad (Pascuales, California, Manta, etc.):
  * DEDUCCIÓN: estado_fisico: "Usado", tipo: "Recibido", destino: "Stock".
- PROVEEDOR -> Si menciona "Proveedor", "Compra", "Importación":
  * DEDUCCIÓN: estado_fisico: "Nuevo", tipo: "Recibido", destino: "Stock".
- DAÑOS -> Si menciona "Roto", "Falla", "Pantalla negra", "No prende", "Trizado":
  * DEDUCCIÓN: estado: "Dañado", destino: "Dañados". (Anota el daño en 'reporte').
- ACCIÓN -> "Recibí/Entró" = Recibido. "Envié/Salió" = Enviado.

4. LÓGICA DE OBSOLETOS (INTELIGENCIA TÉCNICA):
- DETECCIÓN DE HARDWARE: Si detectas procesadores Intel de 9na Gen o inferior (i3/i5/i7 de serie 9000 para abajo) o tecnologías como DDR2, DDR3, Core 2 Duo, Pentium o Celeron:
  * ACCIÓN: Pregunta: "He notado que es tecnología antigua. ¿Quieres enviarlo a la hoja de Obsoletos?".
- Si el usuario dice "no vale", "chatarra" o "muy viejo", marca estado: "Obsoleto" y destino: "Obsoletos".

5. ESPECIFICACIONES TÉCNICAS (SOLO PARA LAPTOPS Y CPU):
- Una vez tengas marca y serie, PREGUNTA UNA VEZ: "¿Deseas añadir especificaciones (RAM, Procesador, Disco)?". 
- Si dice "SÍ", recolecta los datos. Si dice "NO" o ignora la pregunta, no vuelvas a pedirlo.

6. RESPETO A LAS NEGACIONES:
- Si el usuario dice "sin marca", "sin modelo", "no tiene serie", "no tiene cargador":
  * ACCIÓN: Pon "N/A" en el campo y NUNCA vuelvas a preguntar por eso en esta sesión.

7. ESTÁNDARES PARA SINCRONIZADOR.PY:
- Columnas: equipo, marca, serie, cantidad, estado, estado_fisico, tipo, destino, reporte.
- estado: "Bueno", "Dañado", "Obsoleto".
- estado_fisico: "Nuevo", "Usado".

ESTRUCTURA DE SALIDA JSON (EXTRICTAMENTE OBLIGATORIA):
- Si falta información: { "status": "QUESTION", "missing_info": "Lista numerada de TODO lo que falta" }
- Si todo está completo: { "status": "READY", "items": [{...}] }
"""
# ==========================================
# 5. INTERFAZ
# ==========================================
st.title("🧠 LAIA v25.0 - Enlace a Excel")

if "messages" not in st.session_state: st.session_state.messages = []
if "draft" not in st.session_state: st.session_state.draft = None

t1, t2 = st.tabs(["💬 Chat Auditor", "📊 Dashboard Previo"])

with t1:
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if prompt := st.chat_input("¿Qué ingresó a bodega hoy?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        try:
            client = genai.Client(api_key=API_KEY)
            hist = ""
            for m in st.session_state.messages: hist += m["role"].upper() + ": " + m["content"] + "\n"
            
            contexto = SYSTEM_PROMPT + "\n\n--- CONVERSACIÓN ---\n" + hist
            response = client.models.generate_content(model="gemini-2.0-flash-exp", contents=contexto)
            
            raw = response.text
            if "```json" in raw: raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw: raw = raw.split("```")[1].split("```")[0]
            
            res_json = json.loads(raw)
            
            # --- BLINDAJE CONTRA EL ERROR DE LISTA ---
            resp_laia = res_json.get("missing_info", "Necesito más detalles.")
            if isinstance(resp_laia, list): # Si la IA mandó una lista por error
                resp_laia = " . ".join(map(str, resp_laia))
            # -----------------------------------------

            if res_json.get("status") == "READY":
                st.session_state.draft = res_json.get("items", [])
                resp_laia = "✅ ¡Excelente! He recolectado toda la información. ¿Confirmas el envío al buzón?"
            else:
                st.session_state.draft = None

            with st.chat_message("assistant"): st.markdown(resp_laia)
            st.session_state.messages.append({"role": "assistant", "content": resp_laia})
        except Exception as e: 
            st.error("Error IA: " + str(e))
    if st.session_state.draft:
        st.table(pd.DataFrame(st.session_state.draft))
        if st.button("🚀 ENVIAR AL BUZÓN PARA SINCRONIZAR"):
            fecha = (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
            for i in st.session_state.draft: i["fecha"] = fecha
            
            if enviar_github(FILE_BUZON, st.session_state.draft):
                st.success("¡Enviado! Tu script local lo procesará en unos segundos.")
                st.session_state.draft = None
                st.session_state.messages = []
                time.sleep(2)
                st.rerun()

with t2:
    # El dashboard lee el histórico para mostrarte qué hay actualmente
    hist, _ = obtener_github(FILE_HISTORICO)
    if hist:
        df_h = pd.DataFrame(hist)
        # Parche de nombres de columnas para el dashboard de LAIA
        df_h.columns = df_h.columns.str.lower().str.strip()
        if 'estado' in df_h.columns and 'condicion' not in df_h.columns:
            df_h['condicion'] = df_h['estado'] # Compatibilidad visual
        
        st_res, st_det = calcular_stock_web(df_h)
        k1, k2 = st.columns(2)
        k1.metric("📦 Stock en Excel", int(st_res['val'].sum()) if not st_res.empty else 0)
        k2.metric("🚚 Total Movimientos", len(df_h))
        
        st.write("#### Resumen por Estado Físico")
        if not st_res.empty:
            st.dataframe(st_res.pivot_table(index=['equipo','marca'], columns='estado_fisico', values='val', aggfunc='sum').fillna(0))
        st.write("#### Detalle de Series")
        st.dataframe(st_det, use_container_width=True)
    else: st.info("Sincronizando con GitHub...")

if st.sidebar.button("🧹 Limpiar Chat"):
    st.session_state.messages = []
    st.session_state.draft = None
    st.rerun()
