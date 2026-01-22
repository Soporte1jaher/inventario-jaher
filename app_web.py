import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Inventario Jaher PRO", page_icon="🤖", layout="wide")

# --- CREDENCIALES ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Configura los Secrets (GITHUB_TOKEN y GOOGLE_API_KEY) en Streamlit.")
    st.stop()

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Cache-Control": "no-cache"}

# --- FUNCIONES DE APOYO ---
def obtener_fecha_ecuador():
    return (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")

def obtener_github(archivo):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}"
    try:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 200:
            d = resp.json()
            return json.loads(base64.b64decode(d['content']).decode('utf-8')), d['sha']
    except: pass
    return [], None

def enviar_buzon(datos):
    if not isinstance(datos, list): datos = [datos]
    actuales, sha = obtener_github(FILE_BUZON)
    actuales.extend(datos)
    payload = {
        "message": "Web Update LAIA PRO",
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha
    }
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_BUZON}"
    return requests.put(url, headers=HEADERS, json=payload).status_code in [200, 201]

def extraer_json(texto):
    try:
        i = texto.find("[")
        if i == -1: i = texto.find("{")
        f = texto.rfind("]") + 1
        if f <= 0: f = texto.rfind("}") + 1
        return texto[i:f]
    except: return ""

# --- INTERFAZ ---
st.title("🤖 LAIA: Asistente de Inventario Inteligente")
t1, t2, t3, t4 = st.tabs(["📝 Registrar", "💬 Chat IA & Análisis", "🗑️ Borrar", "📊 Historial"])

# --- TAB 1: REGISTRAR (MEJORADO CON ESTADO Y CANTIDAD) ---
with t1:
    st.subheader("📝 Registro de Movimientos Pro")
    st.info("LAIA ahora entiende cantidades y estados (Dañado, Operativo, Reparación, Nuevo).")
    
    texto_input = st.text_area(
        "Describe el movimiento:", 
        placeholder="Ej: llegaron 50 mouses Genius nuevos de Manta y 2 teclados dañados...",
        height=150
    )
    
    if st.button("🚀 Procesar e Ingresar al Inventario", type="primary"):
        if texto_input.strip():
            with st.spinner("LAIA analizando stock, estados y ubicación..."):
                try:
                    client = genai.Client(api_key=API_KEY)
                    prompt = f"""
                    Actúa como experto en logística. Analiza: "{texto_input}"
                    TAREAS:
                    1. CLASIFICACIÓN: 'Recibido' si entra, 'Enviado' si sale.
                    2. CANTIDAD: Extrae el número. Si no hay, es 1.
                    3. ESTADO: Clasifica en 'Operativo', 'Dañado', 'Nuevo' o 'En Reparación'.
                    4. CORRECCIÓN: 'sansum'->'Samsung', 'dell'->'Dell', etc.
                    Devuelve LISTA JSON:
                    [{{
                        "tipo": "Recibido o Enviado",
                        "cantidad": número,
                        "estado": "...",
                        "serie": "...",
                        "marca": "...",
                        "equipo": "...",
                        "accion": "registrar",
                        "ubicacion": "...",
                        "reporte": "..."
                    }}]
                    """
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                    json_limpio = extraer_json(resp.text)
                    
                    if json_limpio:
                        datos_ia = json.loads(json_limpio)
                        if isinstance(datos_ia, dict): datos_ia = [datos_ia]
                        
                        fecha_actual = obtener_fecha_ecuador()
                        for item in datos_ia: item["fecha"] = fecha_actual
                        
                        if enviar_buzon(datos_ia):
                            st.balloons()
                            st.success(f"✅ Registrado con éxito en el sistema.")
                            st.table(pd.DataFrame(datos_ia))
                        else: st.error("❌ Error con GitHub.")
                except Exception as e: st.error(f"❌ Error: {e}")

# --- TAB 2: CHAT IA (MEJORADO: BÚSQUEDA SEMÁNTICA Y PREDICTIVA) ---
with t2:
    st.subheader("💬 Consulta Inteligente y Análisis de Stock")
    if "messages" not in st.session_state: st.session_state.messages = []

    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p_chat := st.chat_input("Ej: ¿Cuántos mouses nos quedan? o ¿Qué llegó de Manta ayer?"):
        st.session_state.messages.append({"role": "user", "content": p_chat})
        with st.chat_message("user"): st.markdown(p_chat)
        
        historial, _ = obtener_github(FILE_HISTORICO)
        
        # PROMPT MAMADÍSIMO PARA CÁLCULOS Y BÚSQUEDA SEMÁNTICA
        contexto = f"""
        Eres LAIA, experta en inventario de Jaher. 
        Datos actuales: {json.dumps(historial[-100:])}
        Hoy es {obtener_fecha_ecuador()}.
        
        Instrucciones:
        1. Si piden stock: Suma 'Recibido' y resta 'Enviado' para ese equipo.
        2. Si preguntan por fallas: Busca los estados 'Dañado'.
        3. Si preguntan por fechas: Filtra los datos semánticamente (ej. 'ayer').
        4. Responde de forma ejecutiva y profesional.
        """
        
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=contexto + f"\nPregunta: {p_chat}")
        
        with st.chat_message("assistant"): st.markdown(resp.text)
        st.session_state.messages.append({"role": "assistant", "content": resp.text})

# --- TAB 3: BORRAR ---
with t3:
    st.subheader("🗑️ Eliminación Inteligente")
    txt_borrar = st.text_area("Dime qué quieres borrar:", placeholder="Ej: borra la serie 12345")
    if st.button("🗑️ EJECUTAR BORRADO"):
        if txt_borrar:
            client = genai.Client(api_key=API_KEY)
            prompt_b = f"Extrae las series de: '{txt_borrar}'. Devuelve JSON: [{{'serie': '...', 'accion': 'borrar'}}]"
            resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_b)
            lista_borrar = json.loads(extraer_json(resp.text))
            if lista_borrar and enviar_buzon(lista_borrar):
                st.warning("✅ Órdenes de borrado enviadas.")

# --- TAB 4: HISTORIAL (COLUMNAS ACTUALIZADAS) ---
with t4:
    if st.button("🔄 Cargar Datos Actuales"):
        datos, _ = obtener_github(FILE_HISTORICO)
        if datos:
            df = pd.DataFrame(datos)
            cols = ["fecha", "tipo", "cantidad", "estado", "serie", "marca", "equipo", "ubicacion", "reporte"]
            df = df.reindex(columns=[c for c in cols if c in df.columns])
            st.dataframe(df, use_container_width=True)
