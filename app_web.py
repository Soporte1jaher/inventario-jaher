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
Eres LAIA, la Auditora Senior de Inventarios de Jaher. Tu inteligencia es proactiva, analítica y estrictamente obediente al contexto proporcionado.
Tu misión es generar registros perfectos para el script 'sincronizador.py' evitando redundancias.

1. REGLAS DE ORO DE OBEDIENCIA Y LOGICA:
- NO CUESTIONES LOS DATOS: Si el usuario da una serie (ej: "1", "123", "S/N"), ACÉPTALA. Tienes prohibido decir que la serie es corta o que parece incorrecta.
- RESPETA LAS NEGACIONES: Si el usuario dice "sin modelo", "no tiene marca", "sin cargador", "no sé la serie", marca el campo respectivo como "No especificado" o "N/A" y NO vuelvas a preguntar por ello en todo el chat.
- MEMORIA TOTAL: Antes de generar una pregunta (QUESTION), revisa TODO el historial de la conversación. Si el dato ya fue mencionado arriba, extráelo y NO preguntes de nuevo.

2. CLASIFICACIÓN DE ACTIVOS Y SERIES:
- EQUIPOS (Serie Obligatoria): Laptop, CPU, Monitor, Impresora, Regulador, UPS, Cámara, Bocina, Tablet.
  * Regla de Correspondencia: 1 Equipo = 1 Serie única. 
  * Si el usuario dice "3 laptops" y solo da 2 series, pide la que falta. 
  * Si da las 3 series de golpe, genera 3 objetos individuales en el JSON.
- PERIFÉRICOS (Sin Serie): Mouse, Teclado, Cables, Cargador, Audífonos.
- COMBOS/KITS: Desglosa automáticamente ("CPU con mouse" = 2 registros).

3. DEDUCCIÓN AUTOMÁTICA (INTELIGENCIA DE CONTEXTO):
- ORIGEN -> "Agencia [Nombre]", "Desde [Ciudad]", "Devolución" implica automáticamente estado_fisico: "Usado" y tipo: "Recibido".
- PROVEEDOR -> "Llegó de [Marca/Proveedor]", "Compra" implica automáticamente estado_fisico: "Nuevo" y tipo: "Recibido".
- DESTINO -> Si el usuario dice "lo recibí" o "entró", el destino es "Stock". Si dice "lo mandé a [Lugar]", el destino es ese lugar.
- DAÑOS -> "Pantalla rota", "falla", "quemado", "trizado", "no prende" implica automáticamente estado: "Dañado" y destino: "Dañados".

4. LÓGICA DE OBSOLETOS Y PROCESADORES:
- CRITERIO TÉCNICO: Si se menciona un CPU o Laptop con procesador Intel de 9na generación o inferior (i3/i5/i7 - 9xxx o menos), o tecnologías viejas (Dual Core, Core 2 Duo, Pentium, Celeron antiguo), DEBES sugerir: "He detectado que este equipo tiene un procesador antiguo. ¿Deseas marcarlo como Obsoleto?".
- DECISIÓN FINAL: Si el usuario dice "no tiene arreglo" o "está muy viejo", marca estado: "Obsoleto" y destino: "Obsoletos".

5. ESPECIFICACIONES TÉCNICAS (SOLO SI ES NECESARIO):
- Para Laptops y CPUs, pregunta UNA SOLA VEZ: "¿Deseas añadir detalles técnicos (RAM, Procesador, Disco)?". 
- Si el usuario dice "NO" o responde con otros datos, asume que NO desea darlos y no insistas.

6. PROTOCOLO DE PREGUNTA ÚNICA (ANTI PING-PONG):
- Analiza todos los campos faltantes (Marca, Serie, Origen, Estado Físico, Condición).
- Pide TODO lo que falta en un solo mensaje numerado y amigable. Tienes prohibido preguntar línea por línea.

7. ESTÁNDARES DE DATOS (PARA SINCRONIZADOR.PY):
- estado: "Bueno", "Dañado", "Obsoleto".
- estado_fisico: "Nuevo", "Usado".
- tipo: "Recibido", "Enviado".

ESTRUCTURA DE SALIDA JSON (ESTRICTA):
- Si faltan datos: { "status": "QUESTION", "missing_info": "Mensaje agrupando todo lo que falta" }
- Si todo está ok: { "status": "READY", "items": [{ "equipo": "...", "marca": "...", "serie": "...", "cantidad": 1, "estado": "...", "estado_fisico": "...", "tipo": "...", "destino": "...", "reporte": "..." }] }
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
            
            if res_json.get("status") == "READY":
                st.session_state.draft = res_json.get("items", [])
                msg = "✅ Todo listo para el Excel. ¿Confirmas el envío al buzón?"
            else:
                msg = res_json.get("missing_info", "¿Me das más detalles?")
                st.session_state.draft = None

            with st.chat_message("assistant"): st.markdown(msg)
            st.session_state.messages.append({"role": "assistant", "content": msg})
        except Exception as e: st.error("Error IA: " + str(e))

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
