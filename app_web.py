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
st.set_page_config(page_title="LAIA v50.0 - Super Auditora", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2e7d32; color: white; border: none; }
    .stChatFloatingInputContainer { background-color: #0e1117; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CREDENCIALES Y APOYO
# ==========================================
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Configura los Secrets (GOOGLE_API_KEY y GITHUB_TOKEN).")
    st.stop()

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"

HEADERS = {"Authorization": "token " + GITHUB_TOKEN, "Cache-Control": "no-cache"}

def extraer_json(texto):
    try:
        texto = texto.replace("```json", "").replace("```", "").strip()
        inicio = texto.find("[")
        if inicio == -1: inicio = texto.find("{")
        fin = texto.rfind("]") + 1
        if fin == 0: fin = texto.rfind("}") + 1
        if inicio != -1 and fin > inicio:
            return texto[inicio:fin].strip()
        return texto
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
# 4. CEREBRO MAESTRO LAIA V50.0
# ==========================================
SYSTEM_PROMPT = """
Eres LAIA, la Auditora Senior de Inventarios de Jaher. Tu única prioridad es la INTEGRIDAD de los datos. 
Si un registro entra incompleto, el inventario no sirve. Por lo tanto, eres extremadamente exigente.

1. REGLA DE BLOQUEO #1 (SERIES OBLIGATORIAS):
- Laptops, CPUs, Monitores, Impresoras, Reguladores, UPS, Cámaras, Bocinas, Tablets.
- SI FALTA LA SERIE, TIENES PROHIBIDO DAR EL STATUS "READY". 
- No importa si el usuario te dio el equipo y la marca; si no hay serie, tu respuesta DEBE ser "QUESTION".

2. REGLA DE BLOQUEO #2 (AGENCIA/ORIGEN):
- No puedes registrar nada si no sabes de dónde viene (Proveedor o Agencia) o a dónde va.
- Si no se menciona el lugar, PREGUNTA: "¿De qué agencia o proveedor es este movimiento?".

3. REGLA DE BLOQUEO #3 (ANTI-RELLENO):
- Tienes ESTRICTAMENTE PROHIBIDO inventar marcas o series como "N/A", "Sin serie", "Genérica" o "Equipo" por tu cuenta.
- El "N/A" solo se permite si el usuario escribe literalmente: "No tiene serie" o "No tiene marca".

4. LISTA DE VERIFICACIÓN MENTAL (HAZ ESTO SIEMPRE):
Antes de responder, revisa este checklist. Si falta algo, status="QUESTION":
   [ ] ¿Tengo el nombre real del equipo? (Ej: Laptop, no "equipo").
   [ ] ¿Tengo la marca?
   [ ] ¿Tengo la serie única para cada unidad?
   [ ] ¿Sé si es Nuevo o Usado?
   [ ] ¿Sé la Agencia o Proveedor?
   [ ] ¿Sé si está Bueno o Dañado?

5. DEDUCCIÓN LÓGICA (PARA NO SER REPETITIVA):
- Menciona Ciudad/Agencia -> Deduces: Usado, Recibido, Stock.
- Menciona Proveedor -> Deduces: Nuevo, Recibido, Stock.
- Menciona Roto/Falla -> Deduces: Dañado, Destino: Dañados.

6. TRADUCCIÓN DE JERGA:
- "Portátil" = Laptop | "Fierro / Case" = CPU | "Pantalla" = Monitor | "Suprimido" = Regulador.

7. MULTI-ORDEN Y COMBOS:
- Desglosa kits: "CPU con mouse" = 2 registros.
- Si envías periféricos, cantidad: 1 y tipo: "Enviado" (para que el Excel reste).

8. PROTOCOLO DE PREGUNTA EN LOTE:
- Si faltan 3 datos, pide los 3 en un solo mensaje profesional: "Entendido el ingreso del CPU Xtech. Para finalizar el registro necesito: 1. El número de serie. 2. La agencia de origen. 3. Si es nuevo o usado."

SALIDA JSON (OBLIGATORIA Y ESTRICTA):
{
  "status": "READY" o "QUESTION",
  "missing_info": "Texto pidiendo los datos REALES faltantes",
  "items": [
    { "equipo": "...", "marca": "...", "serie": "...", "cantidad": 1, "estado": "Bueno/Dañado/Obsoleto", "estado_fisico": "Nuevo/Usado", "tipo": "Recibido/Enviado", "destino": "...", "reporte": "..." }
  ]
}
"""
# ==========================================
# 5. INTERFAZ
# ==========================================
st.title("🧠 LAIA v50.0 - Enlace a Excel")

if "messages" not in st.session_state: st.session_state.messages = []
if "draft" not in st.session_state: st.session_state.draft = None

t1, t2, t3 = st.tabs(["💬 Chat Auditor", "📊 Dashboard Previo", "🗑️ Limpieza"])

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
            
            res_json = json.loads(extraer_json(raw))
            
            if isinstance(res_json, list):
                res_json = {"status": "READY", "items": res_json}
            
            raw_missing = res_json.get("missing_info", "Necesito más detalles.")
            resp_laia = str(raw_missing) if not isinstance(raw_missing, list) else ". ".join(map(str, raw_missing))

            if res_json.get("status") == "READY":
                st.session_state.draft = res_json.get("items", [])
                resp_laia = "✅ ¡Todo capturado! Revisa la tabla y confirma para sincronizar con el Excel."
            else:
                st.session_state.draft = None

            with st.chat_message("assistant"): st.markdown(resp_laia)
            st.session_state.messages.append({"role": "assistant", "content": resp_laia})
        except Exception as e: 
            st.error("Error IA: " + str(e))

    if st.session_state.draft:
        st.write("### 📋 Pre-visualización de Movimientos")
        st.table(pd.DataFrame(st.session_state.draft))
        if st.button("🚀 ENVIAR AL BUZÓN PARA SINCRONIZAR"):
            fecha = (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
            for i in st.session_state.draft: i["fecha"] = fecha
            if enviar_github(FILE_BUZON, st.session_state.draft):
                st.success("✅ ¡Datos enviados!")
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
        k1.metric("📦 Stock en Excel", int(st_res['val'].sum()) if not st_res.empty else 0)
        k2.metric("🚚 Total Movimientos", len(df_h))
        if not st_res.empty:
            st.dataframe(st_res.pivot_table(index=['equipo','marca'], columns='estado_fisico', values='val', aggfunc='sum').fillna(0))
        st.dataframe(st_det, use_container_width=True)
    else: st.info("Sincronizando...")

with t3:
    st.subheader("🗑️ Eliminación y Limpieza Inteligente")
    txt_borrar = st.text_input("Orden de eliminación:", placeholder="Ej: 'Borrar todo lo de HP'")
    if st.button("🔥 EJECUTAR ORDEN DE LIMPIEZA", type="primary"):
        if txt_borrar:
            try:
                client = genai.Client(api_key=API_KEY)
                p_db = "Actúa como DBA. COLUMNAS: [equipo, marca, serie, estado, destino]. ORDEN: " + txt_borrar
                p_db += "\nRESPONDE SOLO JSON: {\"accion\":\"borrar_todo\"} o {\"accion\":\"borrar_filtro\",\"columna\":\"...\",\"valor\":\"...\"}"
                resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=p_db)
                order = json.loads(extraer_json(resp.text))
                if enviar_github(FILE_BUZON, order):
                    st.success("✅ Orden enviada al buzón."); st.json(order)
            except Exception as e: st.error("Error: " + str(e))

if st.sidebar.button("🧹 Borrar Chat"):
    st.session_state.messages = []; st.session_state.draft = None; st.rerun()
