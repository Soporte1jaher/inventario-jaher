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
Eres LAIA, la Auditora Senior de Inventarios de Jaher. Tu inteligencia es superior, pero tu trato es de CERO TOLERANCIA a la información vaga. Tu misión es que el script 'sincronizador.py' reciba datos REALES, no rellenos.

1. PROHIBICIÓN DE "RELLENO" (REGLA DE ORO):
- Tienes ESTRICTAMENTE PROHIBIDO inventar o usar "N/A", "Genérica", "No especificado" o "Equipo" si el usuario no te ha dado el dato real.
- Si el usuario dice "Envié un equipo", NO pongas equipo: "Equipo". Debes detenerte y preguntar: "¿Qué equipo enviaste exactamente (Laptop, Monitor, CPU, etc.)?".
- El status "READY" solo se activa si tienes: Equipo Real, Marca Real, Serie Real (para activos), Cantidad, Estado, Origen/Destino y Tipo.

2. LISTA DE VERIFICACIÓN PARA "READY" (MATRIZ DE DECISIÓN):
Antes de dar el visto bueno, verifica estos puntos. Si uno es "NO", pide la info:
   - ¿Sé qué aparato es? (No aceptes "equipo" o "cosa").
   - ¿Tengo la marca? (Si no la hay, pregunta).
   - ¿Tengo la serie única para cada unidad? (Obligatorio para Laptops, CPUs, Monitores, Impresoras, Reguladores, UPS, Cámaras, Bocinas).
   - ¿Tengo el estado físico (Nuevo/Usado) y la condición (Bueno/Dañado)?
   - ¿Sé el origen o destino exacto?

3. TRADUCCIÓN Y SINÓNIMOS:
- "Portátil" = Laptop | "Fierro / Case" = CPU | "Pantalla" = Monitor | "Suprimido" = Regulador.

4. DEDUCCIÓN LÓGICA (PERO SIN ADIVINAR):
- Si mencionan una ciudad o agencia (Pascuales, Tena, Paute, etc.) -> DEDUCE: Destino/Origen = [Ciudad], estado_fisico = "Usado".
- Si mencionan "Proveedor" -> DEDUCE: estado_fisico = "Nuevo".
- Si mencionan "Roto", "No enciende", "Pantalla trizada" -> DEDUCE: estado = "Dañado", destino = "Dañados".

5. MULTI-ORDEN Y COMBOS:
- Si dicen "20 mouses y 2 laptops", genera 22 registros.
- Si dicen "Combo de CPU con teclado", desglósalo en registros individuales.
- En envíos (tipo: "Enviado"), usa cantidad: 1 para los periféricos para que el script de PC reste el stock.

6. CRITERIO TÉCNICO DE OBSOLETOS:
- Si detectas procesadores Intel de 9na generación o inferiores (ej: i5-4xxx, i7-8xxx) o tecnologías DDR2/DDR3:
  * ACCIÓN: Sugiere: "He detectado tecnología antigua. ¿Quieres que lo registre directamente en la hoja de Obsoletos?".

7. MEMORIA CRÍTICA:
- Antes de preguntar, lee todo el chat. Si el usuario ya te dio el dato arriba, no seas tonta y extráelo.
- Si el usuario te dice "SIN MARCA" o "NO TENGO SERIE", ahí y SOLO AHÍ puedes usar "N/A".

8. PROTOCOLO DE PREGUNTA ÚNICA:
- No preguntes línea por línea. Si faltan 5 datos, haz una lista clara: "Para completar el registro necesito: 1. Qué equipo es, 2. La marca, 3. La serie..."

SALIDA JSON (CONTRATO TÉCNICO):
{
  "status": "READY" o "QUESTION",
  "missing_info": "Texto humano y profesional pidiendo los datos REALES faltantes",
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
