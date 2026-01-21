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
    """Guarda una lista de registros en ambos archivos de una sola vez"""
    exito = True
    
    # 1. ACTUALIZAR BUZÓN
    datos_buzon, sha_buzon = obtener_archivo_github(FILE_BUZON)
    datos_buzon.extend(lista_nuevos_datos) # Agregamos la lista completa
    payload_buzon = {
        "message": f"Registrados {len(lista_nuevos_datos)} equipos",
        "content": base64.b64encode(json.dumps(datos_buzon, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha_buzon if sha_buzon else None
    }
    res_b = requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_BUZON}", 
                         headers=HEADERS_GITHUB, json=payload_buzon)

    # 2. ACTUALIZAR HISTÓRICO
    datos_hist, sha_hist = obtener_archivo_github(FILE_HISTORICO)
    datos_hist.extend(lista_nuevos_datos) # Agregamos la lista completa
    payload_hist = {
        "message": f"Actualizado histórico: +{len(lista_nuevos_datos)} registros",
        "content": base64.b64encode(json.dumps(datos_hist, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha_hist if sha_hist else None
    }
    res_h = requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_HISTORICO}", 
                         headers=HEADERS_GITHUB, json=payload_hist)
    
    return res_b.status_code in [200, 201] and res_h.status_code in [200, 201]

def extraer_json(texto):
    """Función mejorada para extraer listas o celdas individuales"""
    try:
        inicio = min(texto.find("[") if "[" in texto else float('inf'), 
                     texto.find("{") if "{" in texto else float('inf'))
        fin = max(texto.rfind("]") if "]" in texto else -1, 
                  texto.rfind("}") if "}" in texto else -1) + 1
        return texto[int(inicio):int(fin)]
    except:
        return texto

# --- INTERFAZ ---
st.title("🌐 Sistema de Inventario con Memoria Histórica")

tab1, tab2, tab3 = st.tabs(["📝 Registrar", "💬 Consultar IA", "📊 Historial Completo"])

with tab1:
    st.subheader("Registrar nuevo movimiento")
    texto_input = st.text_area("Describe el movimiento (puedes poner varios equipos):", 
                              placeholder="Ej: Laptop HP serie 123 llega de Quito. Laptop Lenovo serie 456 llega de Ambato...")
    
    if st.button("Procesar y Guardar", type="primary"):
        if texto_input:
            with st.spinner("IA analizando datos..."):
                try:
                    client = genai.Client(api_key=API_KEY)
                    # Prompt mejorado para pedir una LISTA obligatoriamente
                    prompt = f"""
                    Analiza: '{texto_input}'. 
                    Extrae cada equipo mencionado y devuélvelos en una LISTA de objetos JSON.
                    Formato: [{{ "serie": "...", "equipo": "...", "accion": "...", "ubicacion": "...", "reporte": "..." }}]
                    Si solo hay uno, igual ponlo dentro de una lista [].
                    Responde SOLO el JSON.
                    """
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                    
                    datos_ia = json.loads(extraer_json(resp.text))
                    
                    # Normalizar: Asegurarnos de que sea una lista
                    if isinstance(datos_ia, dict):
                        datos_ia = [datos_ia]
                    
                    # Añadir fecha a cada registro
                    fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    for item in datos_ia:
                        item["fecha"] = fecha_actual
                    
                    if guardar_datos_masivos(datos_ia):
                        st.success(f"✅ ¡{len(datos_ia)} registros guardados correctamente!")
                        st.balloons()
                    else:
                        st.error("Error al subir a GitHub.")
                except Exception as e:
                    st.error(f"Error procesando los datos: {e}")

with tab2:
    st.subheader("Consulta al Asistente (Memoria del Histórico)")
    pregunta = st.text_input("Pregunta sobre cualquier equipo registrado:")
    
    if st.button("Consultar"):
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
