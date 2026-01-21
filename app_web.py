import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta
import pandas as pd

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Inventario Jaher", layout="wide")

try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Faltan las claves en Secrets.")
    st.stop()

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"
HEADERS_GITHUB = {"Authorization": f"token {GITHUB_TOKEN}"}

def obtener_archivo_github(nombre_archivo):
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

def guardar_datos_en_buzon(lista_datos):
    if isinstance(lista_datos, dict): lista_datos = [lista_datos]
    datos_buzon, sha_buzon = obtener_archivo_github(FILE_BUZON)
    datos_buzon.extend(lista_datos)
    payload = {
        "message": "Orden IA",
        "content": base64.b64encode(json.dumps(datos_buzon, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha_buzon
    }
    res = requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_BUZON}", 
                       headers=HEADERS_GITHUB, json=payload)
    return res.status_code in [200, 201]

def extraer_json(texto):
    """Extrae el bloque JSON de la respuesta de la IA de forma segura"""
    try:
        inicio = texto.find("[")
        if inicio == -1: inicio = texto.find("{")
        fin = texto.rfind("]") + 1
        if fin <= 0: fin = texto.rfind("}") + 1
        
        if inicio != -1 and fin > 0:
            return texto[inicio:fin]
        return ""
    except:
        return ""

# --- INTERFAZ ---
st.title("🌐 Inventario Inteligente Jaher")
tab1, tab2, tab3 = st.tabs(["📝 Registrar Equipo", "💬 Consultar o Borrar", "📊 Ver Historial"])

with tab1:
    st.subheader("Registrar nuevo movimiento")
    texto_input = st.text_area("Describe el equipo (Ej: Laptop Dell serie ABC llega de Manta):", key="reg")
    if st.button("Procesar Registro"):
        if texto_input:
            client = genai.Client(api_key=API_KEY)
            prompt = f"Analiza: {texto_input}. Devuelve SOLO un JSON tipo lista: [{{'serie': '...', 'equipo': '...', 'accion': 'llega', 'ubicacion': '...', 'reporte': '...'}}]"
            resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
            
            # --- VALIDACIÓN SEGURA ---
            json_limpio = extraer_json(resp.text)
            if json_limpio:
                try:
                    datos_ia = json.loads(json_limpio)
                    hora_ec = (datetime.datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                    if isinstance(datos_ia, dict): datos_ia = [datos_ia]
                    for item in datos_ia: item["fecha"] = hora_ec
                    
                    if guardar_datos_en_buzon(datos_ia):
                        st.success("✅ Enviado al Excel.")
                except:
                    st.error("❌ La IA respondió algo extraño. Intenta ser más claro con el equipo.")
            else:
                st.error("❌ No se detectaron datos de equipo. Si quieres borrar, usa la pestaña 'Consultar o Borrar'.")

with tab2:
    st.subheader("Asistente de Consultas y Borrado")
    pregunta = st.text_input("¿Qué quieres hacer? (Ej: '¿Qué hay en Manta?' o 'Borra la serie 12345')")
    if st.button("Ejecutar Acción"):
        if pregunta:
            historial, _ = obtener_archivo_github(FILE_HISTORICO)
            contexto = json.dumps(historial)
            
            prompt_ia = f"""
            Datos actuales: {contexto}
            REGLAS:
            1. Si piden BORRAR, responde SOLAMENTE el JSON: [{{"serie": "LA_SERIE", "accion": "borrar"}}]
            2. Si es una pregunta, responde normal.
            Usuario dice: {pregunta}
            """
            client = genai.Client(api_key=API_KEY)
            resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_ia)
            
            if '"accion": "borrar"' in resp.text:
                json_b = extraer_json(resp.text)
                if json_b:
                    datos_borrado = json.loads(json_b)
                    if guardar_datos_en_buzon(datos_borrado):
                        st.warning(f"🗑️ Orden de borrado enviada para: {datos_borrado[0]['serie']}")
                else:
                    st.error("No pude procesar el borrado.")
            else:
                st.info(resp.text)

with tab3:
    if st.button("Cargar Tabla Actual"):
        datos, _ = obtener_archivo_github(FILE_HISTORICO)
        if datos:
            st.dataframe(pd.DataFrame(datos), use_container_width=True)
