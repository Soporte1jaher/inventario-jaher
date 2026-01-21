import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Inventario Inteligente Jaher", page_icon="🌐", layout="wide")

# --- CREDENCIALES ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Faltan las claves en Secrets (GOOGLE_API_KEY y GITHUB_TOKEN).")
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
        elif resp.status_code == 404:
            # Si el archivo no existe, retornamos lista vacía y SHA None
            return [], None
    except Exception as e:
        st.error(f"Error al leer base de datos: {e}")
    return [], None

def guardar_en_github(nuevo_dato):
    """Agrega un registro nuevo a GitHub"""
    datos_actuales, sha = obtener_datos_github()
    datos_actuales.append(nuevo_dato)
    
    nuevo_json = json.dumps(datos_actuales, indent=4, ensure_ascii=False)
    nuevo_b64 = base64.b64encode(nuevo_json.encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": f"Registro auto: {nuevo_dato.get('equipo', 'nuevo')}",
        "content": nuevo_b64
    }
    if sha:
        payload["sha"] = sha
    
    put_resp = requests.put(URL_GITHUB, headers=HEADERS_GITHUB, json=payload)
    return put_resp.status_code in [200, 201]

def extraer_json(texto):
    """Limpia la respuesta de la IA para obtener solo el JSON"""
    try:
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio != -1 and fin != 0:
            return texto[inicio:fin]
        return texto
    except:
        return texto

# --- INTERFAZ ---
st.title("🌐 Sistema de Inventario con IA")

# Pestañas
tab1, tab2, tab3 = st.tabs(["📝 Registrar Movimiento", "💬 Consultar IA", "📊 Ver Inventario"])

with tab1:
    st.subheader("Registrar nuevo movimiento")
    texto_input = st.text_area("Describe el movimiento:", 
                              placeholder="Ej: Se entregó laptop HP serie 12345 a Juan Perez en la agencia Quito el día de hoy")
    
    if st.button("Procesar y Guardar", type="primary"):
        if texto_input:
            with st.spinner("La IA está analizando los datos..."):
                try:
                    client = genai.Client(api_key=API_KEY)
                    prompt = f"""
                    Analiza el siguiente texto y extrae la información de inventario.
                    Texto: "{texto_input}"
                    
                    Responde ÚNICAMENTE un objeto JSON con estas llaves:
                    - serie: (string o "N/A")
                    - equipo: (tipo de dispositivo)
                    - accion: (entrega, recepción, traslado, etc.)
                    - ubicacion: (ciudad o agencia)
                    - reporte: (resumen breve de quién recibe/entrega)
                    
                    No incluyas explicaciones, solo el JSON puro.
                    """
                    
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                    limpio = extraer_json(resp.text)
                    
                    info = json.loads(limpio)
                    info["fecha"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    if guardar_en_github(info):
                        st.success("✅ ¡Registrado con éxito!")
                        st.json(info) # Mostrar qué se guardó
                        st.balloons()
                    else:
                        st.error("Error al subir a GitHub. Verifica el Token y los permisos.")
                except Exception as e:
                    st.error(f"Error procesando la información: {e}")
        else:
            st.warning("Por favor escribe una descripción.")

with tab2:
    st.subheader("Consulta al Asistente")
    pregunta = st.text_input("Haz una pregunta sobre el inventario:", 
                            placeholder="¿Quién tiene la laptop HP 12345?")
    
    if st.button("Consultar"):
        if pregunta:
            with st.spinner("Consultando registros..."):
                inventario_actual, _ = obtener_datos_github()
                
                if not inventario_actual:
                    st.info("El inventario está vacío actualmente.")
                else:
                    contexto_inventario = json.dumps(inventario_actual, indent=2)
                    
                    prompt_consulta = f"""
                    Eres un asistente de inventario para la empresa Jaher.
                    Aquí tienes la base de datos completa en JSON:
                    {contexto_inventario}
                    
                    Responde de forma clara y amable a la siguiente pregunta basándote solo en los datos proporcionados:
                    "{pregunta}"
                    
                    Si la información no existe, indícalo.
                    """
                    
                    try:
                        client = genai.Client(api_key=API_KEY)
                        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_consulta)
                        st.markdown("---")
                        st.write(resp.text)
                    except Exception as e:
                        st.error(f"Error en la consulta: {e}")

with tab3:
    st.subheader("Registros Históricos")
    if st.button("Actualizar Tabla"):
        datos, _ = obtener_datos_github()
        if datos:
            df = pd.DataFrame(datos)
            # Reordenar columnas para mejor lectura
            columnas = ['fecha', 'equipo', 'serie', 'accion', 'ubicacion', 'reporte']
            df = df[[c for c in columnas if c in df.columns]]
            st.dataframe(df, use_container_width=True)
        else:
            st.write("No hay datos registrados aún.")
