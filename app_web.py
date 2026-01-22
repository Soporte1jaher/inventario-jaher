import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA (ESTÉTICA MAMADA) ---
st.set_page_config(page_title="LAIA NEURAL SYSTEM", page_icon="🧠", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2e7d32; color: white; border: none; }
    .stTextArea>div>div>textarea { background-color: #1a1c23; color: #00ff00; font-family: 'Courier New', monospace; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

# --- CREDENCIALES ---
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
# CORREGIDO: Inyección de Token
HEADERS = {"Authorization": f"token {}", "Cache-Control": "no-cache"}

# --- FUNCIONES DE APOYO (ESTRUCTURA ORIGINAL EXPANDIDA) ---
def obtener_fecha_ecuador():
    return (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")

def obtener_github(archivo):
    url = f"https://api.github.com/repos/{}/{}/contents/{}"
    try:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 200:
            d = resp.json()
            return json.loads(base64.b64decode(d['content']).decode('utf-8')), d['sha']
    except Exception as e:
        pass
    return [], None

def enviar_buzon(datos):
    if not isinstance(datos, list): datos = [datos]
    actuales, sha = obtener_github(FILE_BUZON)
    actuales.extend(datos)
    payload = {
        "message": "LAIA NEURAL UPDATE",
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha
    }
    url = f"https://api.github.com/repos/{}/{}/contents/{}"
    return requests.put(url, headers=HEADERS, json=payload).status_code in [200, 201]

def extraer_json(texto):
    try:
        if "```" in texto:
            texto = texto.split("```")[1]
            if texto.startswith("json"): texto = texto[4:]
        inicio = texto.find("[")
        if inicio == -1: inicio = texto.find("{")
        fin = texto.rfind("]") + 1
        if fin == 0: fin = texto.rfind("}") + 1
        if inicio != -1 and fin > inicio:
            return texto[inicio:fin].strip()
        return texto.strip()
    except: return ""

# --- INTERFAZ ---
st.title("🤖 LAIA NEURAL ENGINE v9.0")
t1, t2, t3, t4 = st.tabs(["📝 Registro Inteligente", "💬 Chat Consultor", "🗑️ Limpieza Quirúrgica", "📊 BI & Historial"])

# --- TAB 1: REGISTRO & ESTRATEGIA (CON MÁS NEURONAS) ---
with t1:
    st.subheader("📝 Gestión de Movimientos")
    st.info("💡 IA Entrena: Puedes dictar órdenes complejas: 'Llegaron 50 mouses, reparte 10 a Manta, 10 a Quito y el resto a bodega'")
    texto_input = st.text_area("Orden Logística:", height=200, placeholder="Escribe aquí el movimiento...")
    
    if st.button("🚀 EJECUTAR ACCIÓN INTELIGENTE", type="primary"):
        if texto_input.strip():
            with st.spinner("LAIA procesando lógica de distribución..."):
                try:
                    client = genai.Client(api_key=API_KEY)
                    prompt = f"""
                    Actúa como un Ingeniero de Datos Logísticos.
                    TEXTO: "{}"
                    TAREAS:
                    1. Clasifica: 'Stock' (periféricos) o 'Movimientos' (equipos con serie).
                    2. Si el texto pide repartir, calcula las cantidades exactas y crea registros individuales.
                    3. Identifica: Marca, Serie, Estado (Nuevo, Usado, Dañado) y Ubicación.
                    FORMATO JSON: [{{ "destino": "...", "tipo": "Recibido/Enviado", "cantidad": n, "equipo": "...", "marca": "...", "serie": "...", "estado": "...", "ubicacion": "...", "reporte": "..." }}]
                    """
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                    json_limpio = extraer_json(resp.text)
                    if json_limpio:
                        datos = json.loads(json_limpio)
                        fecha = obtener_fecha_ecuador()
                        for d in datos: d["fecha"] = fecha
                        if enviar_buzon(datos):
                            st.success(f"✅ LAIA generó {len(datos)} registros.")
                            st.table(pd.DataFrame(datos))
                except Exception as e:
                    st.error(f"Error en IA: {}")

# --- TAB 2: CHAT IA (CON CONTEXTO DE INVENTARIO) ---
with t2:
    st.subheader("💬 Consulta Inteligente")
    if "messages" not in st.session_state: st.session_state.messages = []
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p_chat := st.chat_input("¿Qué equipos tenemos en Ambato?"):
        st.session_state.messages.append({"role": "user", "content": p_chat})
        with st.chat_message("user"): st.markdown(p_chat)
        
        # Inyectamos el historial completo para que la IA responda con la verdad
        hist, _ = obtener_github(FILE_HISTORICO)
        contexto = f"INVENTARIO ACTUAL: {json.dumps(hist[-150:])}. Responde basado solo en estos datos."
        
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=contexto + p_chat)
        
        with st.chat_message("assistant"): st.markdown(resp.text)
        st.session_state.messages.append({"role": "assistant", "content": resp.text})

# --- TAB 3: LIMPIEZA QUIRÚRGICA (LA MAGIA QUE PEDISTE) ---
with t3:
    st.subheader("🗑️ Eliminación por Razonamiento")
    st.warning("⚠️ Aquí puedes ser descriptivo: 'Borra el CPU de Ambato' o 'Borra los mouses dañados'")
    txt_borrar = st.text_input("¿Qué quieres eliminar?")
    
    if st.button("🔥 EJECUTAR BORRADO DE PRECISIÓN"):
        if txt_borrar:
            with st.spinner("LAIA localizando el registro en el historial..."):
                # PASO 1: Obtener historial para que la IA identifique el registro
                hist, _ = obtener_github(FILE_HISTORICO)
                contexto_borrado = json.dumps(hist[-100:]) # Pasamos los últimos 100
                
                client = genai.Client(api_key=API_KEY)
                prompt_b = f"""
                DADOS ESTOS REGISTROS: {contexto_borrado}
                ORDEN DEL USUARIO: "{}"
                TAREA: Identifica qué registro exacto quiere borrar. 
                Responde UNICAMENTE un JSON con este formato:
                [{{"accion": "borrar_quirurgico", "serie": "SERIE_A_BORRAR", "equipo": "NOMBRE", "motivo": "RAZON"}}]
                Si el usuario dice "borra todo", la accion es "borrar_todo".
                """
                resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_b)
                orden_json = extraer_json(resp.text)
                
                if orden_json:
                    if enviar_buzon(json.loads(orden_json)):
                        st.success("🎯 LAIA identificó el registro y envió la orden de eliminación.")
                        st.json(orden_json)
                else:
                    st.error("LAIA no pudo identificar qué registro borrar.")

# --- TAB 4: HISTORIAL & BI (MEJORADO) ---
with t4:
    col1, col2, col3 = st.columns(3)
    datos, _ = obtener_github(FILE_HISTORICO)
    
    if datos:
        df = pd.DataFrame(datos)
        col1.metric("Total Registros", len(df))
        col2.metric("En Stock", len(df[df['destino']=='Stock']))
        col3.metric("Movimientos", len(df[df['destino']=='Movimientos']))
        
        st.subheader("📋 Base de Datos Maestra")
        st.dataframe(df, use_container_width=True)
        
        # Botón para descargar CSV
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Inventario Completo", data=csv, file_name="inventario_jaher.csv", mime="text/csv")
    else:
        st.info("El inventario está vacío.")
