import streamlit as st
from google import genai
import json
import requests
import base64
import datetime

st.set_page_config(page_title="Inventario Inteligente Jaher", page_icon="🌐", layout="wide")

# --- CREDENCIALES ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Faltan las claves en Secrets.")
    st.stop()

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
GITHUB_FILE = "buzon.json"
URL_GITHUB = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE}"
HEADERS_GITHUB = {"Authorization": f"token {GITHUB_TOKEN}"}

# --- FUNCIONES DE GITHUB ---

def obtener_datos_github():
    """Lee el inventario actual desde GitHub"""
    try:
        resp = requests.get(URL_GITHUB, headers=HEADERS_GITHUB)
        if resp.status_code == 200:
            content = resp.json()
            sha = content['sha']
            texto_b64 = content['content']
            texto = base64.b64decode(texto_b64).decode('utf-8')
            return json.loads(texto) if texto.strip() else [], sha
    except Exception as e:
        st.error(f"Error al leer base de datos: {e}")
    return [], None

def guardar_en_github(nuevo_dato):
    """Agrega un registro nuevo a GitHub"""
    datos_actuales, sha = obtener_datos_github()
    datos_actuales.append(nuevo_dato)
    
    nuevo_json = json.dumps(datos_actuales, indent=4)
    nuevo_b64 = base64.b64encode(nuevo_json.encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": f"Registro auto: {nuevo_dato.get('equipo', 'nuevo')}",
        "content": nuevo_b64,
        "sha": sha
    }
    
    put_resp = requests.put(URL_GITHUB, headers=HEADERS_GITHUB, json=payload)
    return put_resp.status_code in [200, 201]

# --- INTERFAZ ---
st.title("🌐 Sistema de Inventario IA")

# Pestañas para separar Registro de Consulta
tab1, tab2 = st.tabs(["📝 Registrar Movimiento", "💬 Chatear con Inventario"])

with tab1:
    st.subheader("Registrar nuevo movimiento")
    texto_input = st.text_area("Describe el movimiento:", placeholder="Ej: Se entregó laptop HP serie 12345 a Juan Perez en Quito")
    
    if st.button("Guardar en Nube", type="primary"):
        if texto_input:
            with st.spinner("La IA está procesando el registro..."):
                try:
                    client = genai.Client(api_key=API_KEY)
                    # Usamos el modelo Flash 2.0 que es el más actual y rápido
                    prompt = f"""Analiza este texto de inventario: "{texto_input}". 
                    Devuelve un objeto JSON con estas llaves: fecha, serie, equipo, accion, ubicacion, reporte. 
                    Sé preciso."""
                    
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                    limpio = resp.text.replace("```json", "").replace("```", "").strip()
                    
                    info = json.loads(limpio)
                    info["fecha"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    if guardar_en_github(info):
                        st.success("✅ ¡Registrado con éxito en GitHub!")
                        st.balloons()
                    else:
                        st.error("Error al subir a GitHub.")
                except Exception as e:
                    st.error(f"Error: {e}")

with tab2:
    st.subheader("Consulta al Asistente")
    pregunta = st.text_input("Haz una pregunta sobre el inventario:", placeholder="¿Está la serie 4567 en el inventario?")
    
    if st.button("Consultar IA"):
        if pregunta:
            with st.spinner("Buscando en los registros..."):
                # 1. Obtener los datos reales de GitHub
                inventario_actual, _ = obtener_datos_github()
                
                # 2. Preparar el contexto para la IA
                # Convertimos el JSON a string para que la IA lo lea
                contexto_inventario = json.dumps(inventario_actual, indent=2)
                
                prompt_consulta = f"""
                Eres un asistente de inventario. Aquí tienes la base de datos actual en formato JSON:
                {contexto_inventario}
                
                Basado EXCLUSIVAMENTE en esos datos, responde la siguiente pregunta del usuario:
                "{pregunta}"
                
                Si no encuentras la información, dilo amablemente.
                """
                
                try:
                    client = genai.Client(api_key=API_KEY)
                    # Usamos Gemini 3 Flash (2.0 Flash) para razonar sobre los datos
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_consulta)
                    st.markdown("### Respuesta:")
                    st.write(resp.text)
                except Exception as e:
                    st.error(f"Error en la consulta: {e}")
