import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Inventario Jaher", page_icon="🌐", layout="wide")

# --- CREDENCIALES ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Error: Faltan las claves GITHUB_TOKEN o GOOGLE_API_KEY en los Secrets de Streamlit.")
    st.stop()

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"
HEADERS_GITHUB = {"Authorization": f"token {GITHUB_TOKEN}", "Cache-Control": "no-cache"}

# --- FUNCIONES DE GITHUB ---

def obtener_archivo_github(nombre_archivo):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{nombre_archivo}"
    try:
        resp = requests.get(url, headers=HEADERS_GITHUB, timeout=10)
        if resp.status_code == 200:
            content = resp.json()
            sha = content['sha']
            texto = base64.b64decode(content['content']).decode('utf-8')
            return json.loads(texto) if texto.strip() else [], sha
        return [], None
    except:
        return [], None

def guardar_datos_en_buzon(lista_datos):
    """Guarda registros en el Buzón para que el PC los procese"""
    if not isinstance(lista_datos, list):
        lista_datos = [lista_datos]
        
    datos_actuales, sha_buzon = obtener_archivo_github(FILE_BUZON)
    datos_actuales.extend(lista_datos)
    
    payload = {
        "message": f"Nueva orden: {len(lista_datos)} registros",
        "content": base64.b64encode(json.dumps(datos_actuales, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha_buzon if sha_buzon else None
    }
    
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_BUZON}"
    resp = requests.put(url, headers=HEADERS_GITHUB, json=payload, timeout=10)
    return resp.status_code in [200, 201]

def extraer_json(texto):
    """Extrae el bloque JSON de la respuesta de la IA"""
    try:
        inicio = texto.find("[")
        if inicio == -1: inicio = texto.find("{")
        fin = texto.rfind("]") + 1
        if fin <= 0: fin = texto.rfind("}") + 1
        if inicio != -1 and fin > 0:
            return texto[inicio:fin]
    except:
        pass
    return ""

# --- LÓGICA DE HORA ECUADOR ---
def obtener_fecha_ecuador():
    # Obtenemos la hora UTC actual y le restamos 5 horas
    utc_now = datetime.datetime.now(timezone.utc)
    ecuador_now = utc_now - timedelta(hours=5)
    return ecuador_now.strftime("%Y-%m-%d %H:%M")

# --- INTERFAZ ---
st.title("🌐 Sistema de Inventario Inteligente Jaher")

tab1, tab2, tab3 = st.tabs(["📝 Registrar Equipo", "💬 Consultar o Borrar", "📊 Ver Historial"])

with tab1:
    st.subheader("Registrar nuevo movimiento")
    texto_input = st.text_area("Describe el equipo y su movimiento:", placeholder="Ej: Laptop HP serie ABC123 llega de Manta con cargador")
    
    if st.button("Procesar y Enviar", type="primary"):
        if texto_input.strip():
            with st.spinner("La IA está analizando los datos..."):
                try:
                    client = genai.Client(api_key=API_KEY)
                    prompt = f"""
                    Analiza el siguiente texto: "{texto_input}"
                    Extrae los datos y devuélvelos estrictamente en formato JSON (una lista de objetos).
                    Campos: serie, equipo, accion, ubicacion, reporte.
                    Si no hay serie, usa 'S/S'.
                    JSON:
                    """
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                    json_texto = extraer_json(resp.text)
                    
                    if json_texto:
                        datos_ia = json.loads(json_texto)
                        if isinstance(datos_ia, dict): datos_ia = [datos_ia]
                        
                        fecha_ec = obtener_fecha_ecuador()
                        for item in datos_ia:
                            item["fecha"] = fecha_ec
                        
                        if guardar_datos_en_buzon(datos_ia):
                            st.success(f"✅ ¡Listo! Se enviaron {len(datos_ia)} equipos al sistema.")
                            st.balloons()
                        else:
                            st.error("Error al conectar con el servidor de datos (GitHub).")
                    else:
                        st.error("La IA no pudo entender el formato. Intenta escribirlo de otra forma.")
                except Exception as e:
                    st.error(f"Ocurrió un error inesperado: {e}")
        else:
            st.warning("Por favor, escribe algo para procesar.")

with tab2:
    st.subheader("Asistente de Consultas y Borrado")
    pregunta = st.text_input("¿Qué deseas hacer? (Ej: '¿Qué hay en Guayaquil?' o 'Borra la serie ABC123')")
    
    if st.button("Ejecutar Acción"):
        if pregunta.strip():
            historial, _ = obtener_archivo_github(FILE_HISTORICO)
            if not historial:
                st.info("El historial está vacío actualmente.")
            else:
                contexto = json.dumps(historial)
                prompt_ia = f"""
                Basado en estos datos de inventario: {contexto}
                
                REGLAS:
                1. Si el usuario quiere BORRAR o ELIMINAR un equipo, responde ÚNICAMENTE con este formato JSON: [{{"serie": "LA_SERIE_A_BORRAR", "accion": "borrar"}}]
                2. Si es una consulta normal, responde de forma clara y breve.
                
                Pregunta del usuario: {pregunta}
                """
                try:
                    client = genai.Client(api_key=API_KEY)
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_ia)
                    
                    # Verificar si es una orden de borrado
                    if '"accion": "borrar"' in resp.text:
                        json_borrar = extraer_json(resp.text)
                        if json_borrar:
                            datos_borrar = json.loads(json_borrar)
                            if guardar_datos_en_buzon(datos_borrar):
                                st.warning(f"🗑️ Orden de eliminación enviada para la serie: {datos_borrar[0]['serie']}. El Excel se actualizará pronto.")
                        else:
                            st.error("Error al procesar la orden de borrado.")
                    else:
                        st.info(resp.text)
                except Exception as e:
                    st.error(f"Error en la consulta: {e}")

with tab3:
    st.subheader("Estado Actual del Inventario")
    if st.button("Actualizar Tabla"):
        datos, _ = obtener_archivo_github(FILE_HISTORICO)
        if datos:
            df = pd.DataFrame(datos)
            # Reordenar columnas para que se vea bien
            columnas = ["fecha", "serie", "equipo", "accion", "ubicacion", "reporte"]
            df = df.reindex(columns=[c for c in columnas if c in df.columns])
            st.dataframe(df, use_container_width=True)
        else:
            st.write("No hay datos registrados en el historial.")
