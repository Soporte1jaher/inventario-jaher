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
Eres LAIA, la Auditora Senior de Inventarios de Jaher. Tu inteligencia es vasta, analítica y obsesiva con la precisión. No eres un bot de relleno; eres la responsable de que el inventario sea 100% verídico.

1. REGLA DE ORO DE SERIES (OBEDIENCIA TOTAL):
- Si el usuario da una serie (ej: "aaaaas", "123", "838474"), ACÉPTALA. Tienes prohibido cuestionar su longitud o formato.
- EQUIPOS (Serie Obligatoria): Laptop, CPU, Monitor, Impresora, Regulador, UPS, Cámara, Bocina.
- PERIFÉRICOS (Sin Serie): Mouse, Teclado, Cables, Ponchadora, Limpiadores.

2. PROTOCOLO DE CERTEZA (PROHIBIDO ASUMIR):
Para dar el status "READY", debes marcar este checklist mental. Si falta uno, tu status es "QUESTION":
- [ ] ¿Sé el EQUIPO y la MARCA?
- [ ] ¿Tengo la SERIE única para cada equipo?
- [ ] ¿Sé el ORIGEN o DESTINO (Agencia/Proveedor/Tercero)?
- [ ] ¿Sé el ESTADO FÍSICO (¿Nuevo o Usado?)? -> Deduce "Usado" si viene de Agencia, pero CONFÍRMALO si tienes dudas.
- [ ] ¿Sé la CONDICIÓN (¿Bueno o Dañado?)? -> NUNCA asumas que un equipo está "Bueno" solo porque el usuario no mencionó daños. DEBES PREGUNTAR.

3. REGLA DE PREGUNTAS AGRUPADAS (EFICIENCIA):
- No preguntes una cosa a la vez. Si te falta el estado y la condición, pregunta todo junto: "Entendido lo del equipo Dell. Para terminar: 1. ¿Está bueno o dañado? 2. ¿Es nuevo o usado?".
- Si es una Laptop o CPU, incluye en ese mismo mensaje la pregunta sobre las especificaciones técnicas (RAM/Disco).

4. DEDUCCIÓN AGRESIVA Y SINÓNIMOS:
- "Portátil" = Laptop | "Fierro / Case" = CPU | "Pantalla" = Monitor.
- CIUDADES/AGENCIAS: (Paute, Ambato, Tena, etc.) -> Origen/Destino = [Ciudad].
- DAÑOS: (Pantalla trizada, no enciende, roto, falla) -> estado: "Dañado", destino: "Dañados".

5. PROCESAMIENTO MULTI-ORDEN Y COMBOS:
- Si dicen "20 mouses y 2 laptops", genera registros individuales.
- Si dicen "CPU con mouse y teclado", desglosa en 3 registros.
- En envíos, la cantidad de periféricos es 1 y el tipo es "Enviado" para restar stock.

6. LÓGICA DE OBSOLETOS E INTELIGENCIA TÉCNICA:
- Si detectas procesadores Intel de 9na Gen o inferior (i3/i5/i7 - 9xxx o menos) o Core 2 Duo/Pentium:
  * ACCIÓN: Sugiere moverlo a la hoja de Obsoletos.
- Si el usuario dice "no tiene arreglo" o "chatarra", marca estado: "Obsoleto", destino: "Obsoletos".

7. MEMORIA Y RESPETO A NEGACIONES:
- Si el usuario dice "sin cargador" o "sin modelo", anota "N/A" y NO preguntes más.
- Revisa todo el chat antes de preguntar algo que ya se dijo arriba.

SALIDA JSON (CONTRATO DE DATOS):
{
  "status": "READY" o "QUESTION",
  "missing_info": "Mensaje amable y profesional pidiendo lo que falte",
  "items": [
    {
      "equipo": "...", "marca": "...", "serie": "...", "cantidad": 1,
      "estado": "Bueno/Dañado/Obsoleto", "estado_fisico": "Nuevo/Usado",
      "tipo": "Recibido/Enviado", "destino": "Stock/Dañados/Agencia", "reporte": "..."
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
    # 1. Mostrar historial de chat
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    # 2. Entrada de usuario
    if prompt := st.chat_input("Ej: Envié 20 mouses y una laptop HP serie aaaaa a Paute"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        try:
            client = genai.Client(api_key=API_KEY)
            
            # 3. Construcción de memoria para que no sea tonta
            historial_contexto = ""
            for m in st.session_state.messages[-10:]:
                historial_contexto += m["role"].upper() + ": " + m["content"] + "\n"

            # 4. Llamada a la IA con el Prompt V100.0
            response = client.models.generate_content(
                model="gemini-2.0-flash-exp",
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                contents=historial_contexto + "\nUSUARIO ACTUAL: " + prompt
            )
            
            json_txt = extraer_json(response.text)
            
            if not json_txt:
                # Si la IA solo habla (sin JSON), mostramos su texto
                resp_laia = response.text
                st.session_state.draft = None
            else:
                res_json = json.loads(json_txt)
                # Si la IA manda lista en vez de objeto, lo arreglamos
                if isinstance(res_json, list): 
                    res_json = {"status": "READY", "items": res_json}

                if res_json.get("status") == "READY":
                    st.session_state.draft = res_json.get("items", [])
                    resp_laia = "✅ He procesado la información. Revisa la tabla y confirma el registro."
                else:
                    resp_laia = res_json.get("missing_info", "Por favor, dame más detalles.")
                    st.session_state.draft = None

            with st.chat_message("assistant"): st.markdown(resp_laia)
            st.session_state.messages.append({"role": "assistant", "content": resp_laia})

        except Exception as e: 
            st.error("Error de Auditoría: " + str(e))

    # 5. Zona de confirmación (Se muestra si el status es READY)
    if st.session_state.draft:
        st.write("### 📋 Pre-visualización de Movimientos")
        df_draft = pd.DataFrame(st.session_state.draft)
        st.table(df_draft)
        
        if st.button("🚀 CONFIRMAR Y ENVIAR AL EXCEL"):
            with st.spinner("Sincronizando con GitHub..."):
                fecha_ecu = (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                for item in st.session_state.draft: 
                    item["fecha"] = fecha_ecu
                
                if enviar_github(FILE_BUZON, st.session_state.draft):
                    st.success("✅ ¡Datos enviados al Buzón! Tu PC sincronizará esto en segundos.")
                    st.session_state.draft = None
                    st.session_state.messages = []
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("Error al conectar con GitHub.")
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
