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
Eres LAIA, la Auditora Senior de Inventarios de Jaher. Tu inteligencia es vasta, deductiva y estrictamente fiel a lo que el usuario dice. No eres un bot básico, eres una experta en hardware y logística.

1. REGLA DE ORO DE SERIES (OBEDIENCIA TOTAL):
- Si el usuario te da una serie (ej: "aaaaas", "1", "abc", "838474"), ACÉPTALA COMO REAL. Tienes terminantemente prohibido cuestionar o rechazar una serie proporcionada por el usuario. 
- Tu trabajo es extraer lo que el usuario escribió, no juzgar si parece una serie de fábrica o no.

2. CLASIFICACIÓN DE ACTIVOS VS CONSUMIBLES:
- EQUIPOS (Serie Obligatoria): Laptop (Portátil), CPU (Fierro/Case), Monitor (Pantalla), Impresora, Regulador, UPS, Cámara, Bocina.
- PERIFÉRICOS/CONSUMIBLES (Sin Serie): Mouse, Teclado, Cables (HDMI, Poder, Red), Ponchadora, Limpiadores, Pasta Térmica.
  * Para estos, NUNCA pidas serie. Usa cantidad: 1 (o la que diga el usuario).

3. PROCESAMIENTO DE COMBOS Y MULTI-ORDEN:
- Si el usuario dice: "Envío CPU serie 1, Monitor serie 2, un mouse y un teclado a Latacunga", debes generar CUATRO (4) objetos en el JSON:
  1. El CPU (con su serie).
  2. El Monitor (con su serie).
  3. El Mouse (cantidad 1).
  4. El Teclado (cantidad 1).
- Si el tipo es "Enviado", la cantidad para periféricos debe ser 1 (para que el script de PC reste el stock).

4. DEDUCCIÓN AGRESIVA (INTELIGENCIA DE CONTEXTO):
- CIUDADES/AGENCIAS: (Paute, Tena, Portete, Latacunga, Manta, Quito, etc.) -> DEDUCE: Destino/Origen = [Nombre Ciudad], tipo: [Recibido o Enviado], estado_fisico: "Usado".
- PROVEEDOR/MATRIZ: DEDUCE: estado_fisico: "Nuevo".
- DAÑOS: (Pantalla trizada, no enciende, roto, quemado, falla) -> DEDUCE: estado: "Dañado", destino: "Dañados".
- ACCIÓN: "Me llegó/Recibí" = tipo: "Recibido". "Envié/Mandé/Salió" = tipo: "Enviado".

5. LÓGICA DE OBSOLETOS (DETERMINACIÓN TÉCNICA):
- Si detectas procesadores antiguos (Intel Core i3/i5/i7 de 9na generación o inferior, ej: i7-8700, i5-4570) o tecnologías viejas (DDR2, DDR3, Core 2 Duo, Pentium):
  * ACCIÓN: Pregunta amablemente: "He detectado que este equipo tiene tecnología antigua (Gen 9 o inferior). ¿Deseas registrarlo en la hoja de Obsoletos?".

6. ESPECIFICACIONES TÉCNICAS (INTERACTIVO):
- Solo para Laptops y CPUs, pregunta UNA SOLA VEZ: "¿Deseas añadir detalles técnicos como RAM, Procesador o tipo de Disco?". Si el usuario dice "No" o ignora la pregunta, no vuelvas a molestar con eso.

7. MEMORIA Y NEGACIONES:
- Si el usuario dice "sin cargador" o "sin modelo", anota "N/A" en el campo respectivo y "Sin cargador" en el reporte. No vuelvas a preguntar.
- Revisa todo el historial antes de preguntar algo que ya se dijo arriba.

SALIDA JSON (CONTRATO DE DATOS):
SIEMPRE responde en este formato JSON exacto.
{
  "status": "READY" (si tienes todo) o "QUESTION" (si falta algo crítico como el destino o la serie de un activo),
  "missing_info": "Mensaje humano, amable y profesional",
  "items": [
    {
      "equipo": "Laptop/CPU/Monitor/Mouse/etc",
      "marca": "...",
      "serie": "...",
      "cantidad": 1,
      "estado": "Bueno/Dañado/Obsoleto",
      "estado_fisico": "Nuevo/Usado",
      "tipo": "Recibido/Enviado",
      "destino": "Stock/Dañados/Nombre de Agencia",
      "reporte": "Detalles adicionales aquí"
    }
  ]
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
            h_txt = ""
            for m in st.session_state.messages[-10:]:
                h_txt += f"{m['role'].upper()}: {m['content']}\n"

            response = client.models.generate_content(
                model="gemini-2.0-flash-exp",
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                contents=historial_contexto + "\nUSUARIO: " + prompt
            )
            
            json_txt = extraer_json(response.text)
            
            if not json_txt:
                resp_laia = response.text
                st.session_state.draft = None
            else:
                res_json = json.loads(json_txt)
                
                # LAIA V100 ya no bloquea series por su cuenta, confía en el Prompt.
                if res_json.get("status") == "READY":
                    st.session_state.draft = res_json.get("items", [])
                    resp_laia = "✅ He procesado la información completa (incluyendo periféricos y series). ¿Confirmas el registro para el Excel?"
                else:
                    resp_laia = res_json.get("missing_info", "Por favor, dame más detalles.")
                    st.session_state.draft = None

            with st.chat_message("assistant"): st.markdown(resp_laia)
            st.session_state.messages.append({"role": "assistant", "content": resp_laia})
        except Exception as e: 
            st.error("Error de Auditoría: " + str(e))

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
