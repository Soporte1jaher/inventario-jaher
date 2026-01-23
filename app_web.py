import streamlit as st
from google import genai
from google.genai import types
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
st.set_page_config(page_title="LAIA v91.0 - Auditora Senior", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2e7d32; color: white; border: none; }
    .stChatFloatingInputContainer { background-color: #0e1117; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CREDENCIALES
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

HEADERS = {"Authorization": "token " + GITHUB_TOKEN, "Cache-Control": "no-cache"}

def extraer_json(texto):
    try:
        texto = texto.replace("```json", "").replace("```", "").strip()
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio != -1 and fin > inicio:
            return texto[inicio:fin].strip()
        return ""
    except:
        return ""

def obtener_github(archivo):
    url = "https://api.github.com/repos/" + GITHUB_USER + "/" + GITHUB_REPO + "/contents/" + archivo
    try:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 200:
            d = resp.json()
            return json.loads(base64.b64decode(d['content']).decode('utf-8')), d['sha']
    except: pass
    return [], None

def enviar_github(archivo, datos, mensaje="LAIA Update"):
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
# 3. MOTOR DE STOCK
# ==========================================
def calcular_stock_web(df):
    if df.empty: return pd.DataFrame(), pd.DataFrame()
    df_c = df.copy()
    df_c.columns = df_c.columns.str.lower().str.strip()
    cols = ['estado', 'estado_fisico', 'tipo', 'destino', 'equipo', 'marca', 'cantidad']
    for col in cols:
        if col not in df_c.columns: df_c[col] = "No especificado"
    df_c['cant_n'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(1)
    def procesar_fila(row):
        est, t, d = str(row.get('estado','')).lower(), str(row.get('tipo','')).lower(), str(row.get('destino','')).lower()
        if 'dañ' in est or 'obs' in est: return 0
        if d == 'stock' or 'recibido' in t: return row['cant_n']
        if 'enviado' in t: return -row['cant_n']
        return 0
    df_c['val'] = df_c.apply(procesar_fila, axis=1)
    resumen = df_c.groupby(['equipo', 'marca', 'estado_fisico'])['val'].sum().reset_index()
    return resumen[resumen['val'] > 0], df_c[df_c['val'] != 0]

# ==========================================
# 4. CEREBRO SUPREMO LAIA V91.0
# ==========================================
SYSTEM_PROMPT = """
Eres LAIA, Auditora Senior de Jaher. Tu trato es amable y humano, pero eres implacable con la precisión de los datos.

REGLAS DE ORO (PROHIBIDO OLVIDAR):
1. NO INVENTES: Tienes prohibido usar "N/A" o "Equipo" si el usuario no te ha dado el dato real.
2. SERIES 1:1: Si entran 3 laptops, DEBES pedir 3 series. No des el READY sin ellas.
3. DEDUCCIÓN: Si mencionan una ciudad (Paute, Tena, etc.), asume que es el destino/origen y que el equipo es usado.
4. PERIFÉRICOS: Mouses, teclados, cables, ponchadoras y limpiadores NO necesitan serie. Agrúpalos por cantidad.
5. SINÓNIMOS: Portátil=Laptop, Fierro=CPU, Pantalla=Monitor.
6. TRATO: Sé cordial. Si faltan datos, pídelos todos en una sola respuesta amable.
7. OBSOLETOS: Si el procesador es Intel 9na Gen o inferior, sugiere moverlo a la hoja de obsoletos.
8. NEGACIONES: Si el usuario dice "sin cargador", anótalo en reporte y no preguntes más.

TU SALIDA DEBE SER SIEMPRE UN JSON CON ESTE FORMATO:
{
  "status": "READY" o "QUESTION",
  "missing_info": "Tu mensaje amable aquí",
  "items": [{"equipo":"...", "marca":"...", "serie":"...", "cantidad":1, "estado":"Bueno/Dañado", "estado_fisico":"Nuevo/Usado", "tipo":"Recibido/Enviado", "destino":"...", "reporte":"..."}]
}
"""

# ==========================================
# 5. INTERFAZ
# ==========================================
st.title("🧠 LAIA v91.0 - Auditoría Senior")

if "messages" not in st.session_state: st.session_state.messages = []
if "draft" not in st.session_state: st.session_state.draft = None

t1, t2, t3 = st.tabs(["💬 Chat Auditor", "📊 Dashboard Previo", "🗑️ Limpieza"])

with t1:
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if prompt := st.chat_input("Ej: Envié un CPU HP serie 123 a Tena"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        try:
            client = genai.Client(api_key=API_KEY)
            # Construimos el historial para que no tenga memoria de pez
            historial_contexto = ""
            for m in st.session_state.messages[-5:]:
                historial_contexto += f"{m['role'].upper()}: {m['content']}\n"

            response = client.models.generate_content(
                model="gemini-2.0-flash-exp",
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                contents=historial_contexto + "\nUSUARIO: " + prompt
            )
            
            json_txt = extraer_json(response.text)
            
            if not json_txt:
                # Si la IA solo habló sin mandar JSON
                resp_laia = response.text
                st.session_state.draft = None
            else:
                res_json = json.loads(json_txt)
                
                # Seguridad: Si la IA mandó READY pero con datos basura (como serie N/A)
                items = res_json.get("items", [])
                for it in items:
                    if str(it.get("serie")).upper() in ["N/A", "NONE"] and str(it.get("equipo")).lower() in ["laptop", "cpu", "monitor"]:
                        res_json["status"] = "QUESTION"
                        res_json["missing_info"] = "Necesito el número de serie real para poder registrar este equipo."

                if res_json.get("status") == "READY":
                    st.session_state.draft = res_json.get("items", [])
                    resp_laia = "✅ He verificado los datos y están completos. ¿Confirmas el registro?"
                else:
                    resp_laia = res_json.get("missing_info", "Por favor, dame más detalles.")
                    st.session_state.draft = None

            with st.chat_message("assistant"): st.markdown(resp_laia)
            st.session_state.messages.append({"role": "assistant", "content": resp_laia})
        except Exception as e: 
            st.error("Error de Procesamiento: " + str(e))

    if st.session_state.draft:
        st.write("### 📋 Pre-visualización")
        st.table(pd.DataFrame(st.session_state.draft))
        if st.button("🚀 ENVIAR AL EXCEL"):
            fecha_ecu = (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
            for i in st.session_state.draft: i["fecha"] = fecha_ecu
            if enviar_github(FILE_BUZON, st.session_state.draft):
                st.success("✅ ¡Datos enviados al Sincronizador!")
                st.session_state.draft = None
                st.session_state.messages = []
                time.sleep(2)
                st.rerun()

with t2:
    hist, _ = obtener_github(FILE_HISTORICO)
    if hist:
        df_h = pd.DataFrame(hist)
        df_h.columns = df_h.columns.str.lower().str.strip()
        st_res, st_det = calcular_stock_web(df_h)
        k1, k2 = st.columns(2)
        k1.metric("📦 Stock Total", int(st_res['val'].sum()) if not st_res.empty else 0)
        k2.metric("🚚 Movimientos", len(df_h))
        if not st_res.empty:
            st.dataframe(st_res.pivot_table(index=['equipo','marca'], columns='estado_fisico', values='val', aggfunc='sum').fillna(0))
        st.dataframe(st_det, use_container_width=True)
    else: st.info("Sincronizando con GitHub...")

with t3:
    st.subheader("🗑️ Limpieza Inteligente")
    txt_borrar = st.text_input("¿Qué deseas eliminar?")
    if st.button("🔥 EJECUTAR BORRADO"):
        if txt_borrar:
            try:
                client = genai.Client(api_key=API_KEY)
                p_db = "Actúa como DBA. COLUMNAS: [equipo, marca, serie, estado, destino]. ORDEN: " + txt_borrar
                p_db += "\nRESPONDE SOLO JSON: {\"accion\":\"borrar_todo\"} o {\"accion\":\"borrar_filtro\",\"columna\":\"...\",\"valor\":\"...\"}"
                resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=p_db)
                order = json.loads(extraer_json(resp.text))
                if enviar_github(FILE_BUZON, order):
                    st.success("✅ Orden enviada."); st.json(order)
            except Exception as e: st.error("Error: " + str(e))

if st.sidebar.button("🧹 Borrar Chat"):
    st.session_state.messages = []; st.session_state.draft = None; st.rerun()
