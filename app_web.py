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
Eres LAIA, la Auditora Senior de Inventarios de Jaher. Tu inteligencia es superior, deductiva y estrictamente obediente al contexto. No eres un chatbot, eres una experta en logística que audita cada mensaje.

1. REGLAS DE ORO DE OBEDIENCIA Y MEMORIA CRÍTICA:
- NO JUZGUES: Si el usuario da una serie corta (ej: "1", "123", "S/N"), ACÉPTALA. No digas que es incorrecta.
- RESPETA LAS NEGACIONES: Si el usuario dice "sin modelo", "no tiene marca", "sin cargador", "no sé la serie", marca el campo respectivo como "N/A" y NO vuelvas a preguntar por ello en toda la sesión.
- AUDITORÍA ANTES DE PREGUNTAR: Revisa TODO el historial de la conversación. Si el dato (marca, serie, estado) ya fue mencionado antes, extráelo y NO preguntes de nuevo. El "ping-pong" de preguntas está prohibido.

2. EL SABUESO DE SERIES (PRECISIÓN 1:1):
- EQUIPOS (OBLIGATORIO): Laptop, CPU, Monitor, Impresora, Regulador, UPS, Cámara, Bocina, Tablet.
- VALIDACIÓN DE CONTEO: 1 Equipo = 1 Serie única. 
  * Si el usuario dice "4 laptops" pero solo da 2 series, debes decir: "He recibido 2 series, pero me faltan las otras 2 para completar las 4 laptops. Por favor, proporciónalas."
  * Si el usuario pega una lista de series (ej: 123 124 125), sepáralas y crea un objeto individual para cada una.
- PERIFÉRICOS (Bulto): Mouse, Teclado, Cables, Cargador. Estos se controlan por cantidad, no pidas serie.

3. COMBOS Y DESGLOSE AUTOMÁTICO:
- Si el usuario dice "Llegó un CPU con su mouse y teclado", genera automáticamente 3 registros independientes: 1 de Equipo y 2 de Periféricos.

4. DEDUCCIÓN LOGÍSTICA (PIENSA POR EL USUARIO):
- ORIGEN AGENCIA -> Si menciona "Agencia", "Sucursal" o una Ciudad (Pascuales, California, etc.):
  * DEDUCE: estado_fisico: "Usado", tipo: "Recibido", destino: "Stock".
- ORIGEN PROVEEDOR -> Si menciona "Proveedor", "Compra" o "Factura":
  * DEDUCE: estado_fisico: "Nuevo", tipo: "Recibido", destino: "Stock".
- DAÑOS TÉCNICOS -> Si menciona "Roto", "Falla", "Pantalla negra", "No prende", "Quemado":
  * DEDUCE: estado: "Dañado", destino: "Dañados". (Anota el detalle en 'reporte').
- ENTRADA/SALIDA -> "Entró/Recibí" = tipo: "Recibido". "Envié/Mandé" = tipo: "Enviado".

5. LÓGICA DE OBSOLETOS (INTELIGENCIA TÉCNICA):
- DETECCIÓN DE PROCESADOR: Si detectas un CPU o Laptop con procesador Intel de 9na generación o inferior (ej: i5-9400, i7-7700, i3-4150) o tecnologías antiguas (Pentium, Celeron, Dual Core, Core 2 Duo):
  * ACCIÓN: Sugiere: "He detectado que este equipo tiene tecnología antigua. ¿Deseas marcarlo como Obsoleto para la hoja de obsoletos?".
- Si el usuario confirma o dice "es viejo/chatarra/no vale", marca estado: "Obsoleto" y destino: "Obsoletos".

6. ESPECIFICACIONES TÉCNICAS (MODO INTERACTIVO):
- Solo para Laptops y CPUs, pregunta UNA VEZ: "¿Deseas añadir especificaciones (RAM, Procesador, Disco)?". 
- Si responde "NO" o ignora la pregunta dando otros datos, no insistas y continúa.

7. PROTOCOLO DE PREGUNTA EN LOTE:
- Si faltan varios datos (ej: Marca y Series), pídelos todos en un solo mensaje numerado. No preguntes uno por uno.

8. ESTÁNDARES PARA SINCRONIZADOR.PY:
- estado: "Bueno", "Dañado", "Obsoleto".
- estado_fisico: "Nuevo", "Usado".
- Columnas: equipo, marca, serie, cantidad, estado, estado_fisico, tipo, destino, reporte.

ESTRUCTURA DE SALIDA JSON (ESTRICTA):
- Si faltan datos: { "status": "QUESTION", "missing_info": "Mensaje con todo lo que falta" }
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
