import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Inventario Jaher", page_icon="🤖", layout="wide")

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
    except:
        pass
    return [], None

def enviar_buzon(datos):
    if not isinstance(datos, list): datos = [datos]
    actuales, sha = obtener_github(FILE_BUZON)
    actuales.extend(datos)
    payload = {
        "message": "Web Update",
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
    except:
        return ""

# --- INTERFAZ ---
st.title("🤖 Asistente de Inventario Jaher")
t1, t2, t3, t4 = st.tabs(["📝 Registrar", "💬 Chat IA", "🗑️ Borrar", "📊 Historial"])

# --- TAB 1: REGISTRAR ---
with t1:
    st.subheader("📝 Registro de Movimientos ")
    st.info("La IA clasificará automáticamente: Tipo (Recibido/Enviado), Marca, Equipo y Ubicación.")
    
    texto_input = st.text_area(
        "Describe el movimiento:", 
        placeholder="Ej: llega de manta un monitor sansum serie 12345 con su base y cable de poder se guarda en bodega",
        height=150
    )
    
    if st.button("🚀 Procesar e Ingresar al Inventario", type="primary"):
        if texto_input.strip():
            with st.spinner("La IA está analizando y corrigiendo el registro..."):
                try:
                    client = genai.Client(api_key=API_KEY)
                    prompt = f"""
                    Actúa como experto en logística. Analiza: "{texto_input}"
                    TAREAS:
                    1. CLASIFICACIÓN: 'Recibido' si entra/llega, 'Enviado' si sale/se va.
                    2. CORRECCIÓN: Corrige marcas y nombres (ej: 'sansum' -> 'Samsung').
                    3. EXTRACCIÓN: Separa Marca de Equipo.
                    Devuelve LISTA JSON:
                    [{{
                        "tipo": "Recibido o Enviado",
                        "serie": "...",
                        "marca": "...",
                        "equipo": "...",
                        "accion": "...",
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
                        for item in datos_ia:
                            item["fecha"] = fecha_actual
                        
                        if enviar_buzon(datos_ia):
                            st.balloons()
                            st.success(f"✅ Registro exitoso ({fecha_actual})")
                            st.table(pd.DataFrame(datos_ia))
                        else:
                            st.error("❌ Error al conectar con GitHub.")
                    else:
                        st.error("❌ La IA no entendió el mensaje. Intenta ser más claro.")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
        else:
            st.warning("⚠️ Escribe algo primero.")

# --- TAB 2: CHAT IA ---
with t2:
    st.subheader("💬 Consulta Inteligente")
    if "messages" not in st.session_state: 
        st.session_state.messages = []

    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p_chat := st.chat_input("¿Qué deseas saber del inventario?"):
        st.session_state.messages.append({"role": "user", "content": p_chat})
        with st.chat_message("user"): st.markdown(p_chat)
        
        historial, _ = obtener_github(FILE_HISTORICO)
        full_p = f"Datos actuales: {json.dumps(historial)}. Pregunta: {p_chat}. Responde profesionalmente."
        
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=full_p)
        
        with st.chat_message("assistant"): st.markdown(resp.text)
        st.session_state.messages.append({"role": "assistant", "content": resp.text})

# --- TAB 3: BORRAR ---
with t3:
    st.subheader("🗑️ Eliminación Inteligente")
    txt_borrar = st.text_area("Dime qué quieres borrar:", placeholder="Ej: borra la serie 12345 y la serie 67890")
    
    if st.button("🗑️ EJECUTAR BORRADO"):
        if txt_borrar:
            with st.spinner("Procesando órdenes de borrado..."):
                client = genai.Client(api_key=API_KEY)
                prompt_b = f"Extrae las series de este texto: '{txt_borrar}'. Devuelve LISTA JSON: [{{'serie': '...', 'accion': 'borrar'}}]"
                resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_b)
                
                lista_borrar = json.loads(extraer_json(resp.text))
                if lista_borrar:
                    if enviar_buzon(lista_borrar):
                        st.warning("✅ Órdenes de borrado enviadas.")
                        st.json(lista_borrar)
                else:
                    st.error("No se detectaron series.")

# --- TAB 4: HISTORIAL ---
with t4:
    if st.button("🔄 Cargar Datos Actuales"):
        datos, _ = obtener_github(FILE_HISTORICO)
        if datos:
            df = pd.DataFrame(datos)
            # Ordenar columnas para que se vea pro
            cols = ["fecha", "tipo", "serie", "marca", "equipo", "accion", "ubicacion", "reporte"]
            df = df.reindex(columns=[c for c in cols if c in df.columns])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("El inventario está vacío.")
