import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
import pandas as pd

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Inventario Inteligente Jaher", page_icon="🌐", layout="wide")

try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Faltan las claves en Secrets.")
    st.stop()

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
# USAMOS DOS ARCHIVOS
FILE_BUZON = "buzon.json"    # El que SharePoint lee y borra
FILE_HISTORICO = "historico.json" # El que la IA usa como memoria eterna
HEADERS_GITHUB = {"Authorization": f"token {GITHUB_TOKEN}"}

# --- FUNCIONES DE GITHUB ---

def obtener_archivo_github(nombre_archivo):
    """Lee cualquier archivo JSON desde GitHub"""
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{nombre_archivo}"
    try:
        resp = requests.get(url, headers=HEADERS_GITHUB)
        if resp.status_code == 200:
            content = resp.json()
            sha = content['sha']
            texto = base64.b64decode(content['content']).decode('utf-8')
            return json.loads(texto) if texto.strip() else [], sha
        return [], None
    except:
        return [], None

def guardar_doble_registro(nuevo_dato):
    """Guarda el dato en el buzón (para SharePoint) y en el histórico (para la IA)"""
    exito = True
    
    # 1. ACTUALIZAR BUZÓN (Lo que se borrará)
    datos_buzon, sha_buzon = obtener_archivo_github(FILE_BUZON)
    datos_buzon.append(nuevo_dato)
    payload_buzon = {
        "message": "Nuevo registro para SharePoint",
        "content": base64.b64encode(json.dumps(datos_buzon, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha_buzon if sha_buzon else None
    }
    res_b = requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_BUZON}", 
                         headers=HEADERS_GITHUB, json=payload_buzon)

    # 2. ACTUALIZAR HISTÓRICO (La memoria de la IA)
    datos_hist, sha_hist = obtener_archivo_github(FILE_HISTORICO)
    datos_hist.append(nuevo_dato)
    payload_hist = {
        "message": "Actualizando histórico para IA",
        "content": base64.b64encode(json.dumps(datos_hist, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha_hist if sha_hist else None
    }
    res_h = requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_HISTORICO}", 
                         headers=HEADERS_GITHUB, json=payload_hist)
    
    return res_b.status_code in [200, 201] and res_h.status_code in [200, 201]

def extraer_json(texto):
    try:
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        return texto[inicio:fin]
    except: return texto

# --- INTERFAZ ---
st.title("🌐 Sistema de Inventario con Memoria Histórica")

tab1, tab2, tab3 = st.tabs(["📝 Registrar", "💬 Consultar IA", "📊 Historial Completo"])

with tab1:
    st.subheader("Registrar nuevo movimiento")
    texto_input = st.text_area("Describe el movimiento:")
    
    if st.button("Procesar y Guardar", type="primary"):
        if texto_input:
            with st.spinner("IA procesando..."):
                client = genai.Client(api_key=API_KEY)
                prompt = f"Analiza: '{texto_input}'. Devuelve SOLO un JSON con: serie, equipo, accion, ubicacion, reporte."
                resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                
                try:
                    info = json.loads(extraer_json(resp.text))
                    info["fecha"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    if guardar_doble_registro(info):
                        st.success("✅ Guardado en Buzón y en Histórico.")
                    else:
                        st.error("Error al guardar en GitHub.")
                except Exception as e:
                    st.error(f"Error de formato: {e}")

with tab2:
    st.subheader("Consulta al Asistente (Memoria del Histórico)")
    pregunta = st.text_input("Pregunta sobre cualquier equipo registrado:")
    
    if st.button("Consultar"):
        # AQUÍ LA IA LEE EL HISTÓRICO, NO EL BUZÓN
        inventario_completo, _ = obtener_archivo_github(FILE_HISTORICO)
        
        if not inventario_completo:
            st.warning("No hay datos en el histórico todavía.")
        else:
            contexto = json.dumps(inventario_completo, indent=2)
            prompt_consulta = f"Datos de inventario:\n{contexto}\n\nPregunta: {pregunta}"
            
            client = genai.Client(api_key=API_KEY)
            resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_consulta)
            st.info(resp.text)

with tab3:
    st.subheader("Todos los registros acumulados")
    if st.button("Cargar Historial"):
        datos, _ = obtener_archivo_github(FILE_HISTORICO)
        if datos:
            st.dataframe(pd.DataFrame(datos), use_container_width=True)
        else:
            st.write("Historial vacío.")
