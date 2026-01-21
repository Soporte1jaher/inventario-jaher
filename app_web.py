import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta
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
FILE_BUZON = "buzon.json"  
FILE_HISTORICO = "historico.json" 
HEADERS_GITHUB = {"Authorization": f"token {GITHUB_TOKEN}"}

# --- FUNCIONES DE GITHUB ---

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

def guardar_datos_masivos(lista_nuevos_datos):
    """Guarda registros en el Buzón (para Excel) y en el Histórico (para la IA)"""
    # 1. Actualizar Buzón
    datos_buzon, sha_buzon = obtener_archivo_github(FILE_BUZON)
    datos_buzon.extend(lista_nuevos_datos)
    payload_buzon = {
        "message": f"Nuevos registros: {len(lista_nuevos_datos)}",
        "content": base64.b64encode(json.dumps(datos_buzon, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha_buzon if sha_buzon else None
    }
    res_b = requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_BUZON}", 
                         headers=HEADERS_GITHUB, json=payload_buzon)

    # 2. Actualizar Histórico
    datos_hist, sha_hist = obtener_archivo_github(FILE_HISTORICO)
    datos_hist.extend(lista_nuevos_datos)
    payload_hist = {
        "message": "Actualización histórico",
        "content": base64.b64encode(json.dumps(datos_hist, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha_hist if sha_hist else None
    }
    res_h = requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_HISTORICO}", 
                         headers=HEADERS_GITHUB, json=payload_hist)
    
    return res_b.status_code in [200, 201] and res_h.status_code in [200, 201]

def extraer_json(texto):
    try:
        inicio = texto.find("[")
        if inicio == -1: inicio = texto.find("{")
        fin = texto.rfind("]") + 1
        if fin <= 0: fin = texto.rfind("}") + 1
        return texto[inicio:fin]
    except: return texto

# --- INTERFAZ ---
st.title("🌐 Sistema de Inventario Jaher")

tab1, tab2, tab3 = st.tabs(["📝 Registrar Movimiento", "💬 Consultar IA", "📊 Ver Historial"])

with tab1:
    st.subheader("Registrar nuevo movimiento")
    texto_input = st.text_area("Describe el movimiento (Ej: Laptop Dell serie ABC llega de Manta con cargador):")
    
    if st.button("Procesar y Guardar", type="primary"):
        if texto_input:
            with st.spinner("La IA está analizando los datos..."):
                try:
                    client = genai.Client(api_key=API_KEY)
                    prompt = f"""
                    Analiza: "{texto_input}"
                    REGLAS:
                    1. Si el equipo trae accesorios (cargador, mouse, etc.), ponlo TODO EN UNA SOLA FILA. No separes el cargador en otra fila.
                    2. Si hay varios equipos distintos, usa una fila para cada equipo principal.
                    3. Campos: serie (si no hay usa 'S/S'), equipo, accion, ubicacion, reporte (menciona los accesorios aquí).
                    Devuelve una LISTA JSON: [{{...}}, {{...}}]
                    """
                    
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                    datos_ia = json.loads(extraer_json(resp.text))
                    if isinstance(datos_ia, dict): datos_ia = [datos_ia]

                    # HORA ECUADOR (UTC-5)
                    hora_ec = (datetime.datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                    
                    for item in datos_ia:
                        item["fecha"] = hora_ec
                    
                    if guardar_datos_masivos(datos_ia):
                        st.success(f"✅ Se registraron {len(datos_ia)} equipos.")
                        st.balloons()
                    else:
                        st.error("Error al guardar en GitHub.")
                except Exception as e:
                    st.error(f"Error: {e}")

with tab2:
    st.subheader("Asistente Inteligente")
    pregunta = st.text_input("¿Qué deseas hacer? (Ej: 'Borra el equipo con serie ABC')")
    
    if st.button("Ejecutar"):
        historial, _ = obtener_archivo_github(FILE_HISTORICO)
        contexto = json.dumps(historial, indent=2)
        
        prompt_especial = f"""
        Actúa como un administrador de base de datos.
        Datos actuales: {contexto}
        
        Si el usuario quiere BORRAR un equipo, responde ÚNICAMENTE con este JSON:
        {{"accion": "BORRAR", "serie": "aquí_el_numero_de_serie"}}
        
        Si el usuario solo está preguntando, responde normal.
        
        Usuario dice: {pregunta}
        """
        
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_especial)
        respuesta_ia = resp.text

        if '"accion": "BORRAR"' in respuesta_ia:
            # Extraer el JSON de borrado
            datos_borrado = json.loads(extraer_json(respuesta_ia))
            # Mandar al buzón como una orden especial
            orden = {
                "tipo": "BORRAR",
                "serie": datos_borrado["serie"],
                "fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            if guardar_datos_masivos([orden]):
                st.warning(f"⚠️ Orden de eliminación enviada para la serie: {datos_borrado['serie']}. Se procesará en unos segundos en tu Excel.")
        else:
            st.info(respuesta_ia)

with tab3:
    st.subheader("Registros en el Histórico")
    if st.button("Cargar Tabla"):
        datos, _ = obtener_archivo_github(FILE_HISTORICO)
        if datos:
            st.dataframe(pd.DataFrame(datos), use_container_width=True)
