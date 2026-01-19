import streamlit as st
from google import genai
import json
import requests
import base64
import datetime

st.set_page_config(page_title="Inventario Web", page_icon="🌐")

# --- CREDENCIALES ---
try:
    # Leemos las claves de la Caja Fuerte de Streamlit
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Faltan las claves en Secrets (Google o GitHub).")
    st.stop()

# --- DATOS GITHUB ---
# (Asegúrate de que estos datos sean correctos)
GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
GITHUB_FILE = "buzon.json"

def guardar_en_github(nuevo_dato):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    datos_actuales = []
    sha = None
    
    # 1. Intentar leer lo que hay
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            content = resp.json()
            sha = content['sha']
            texto_b64 = content['content']
            # Decodificar
            texto = base64.b64decode(texto_b64).decode('utf-8')
            
            # Si el archivo tiene texto, intentamos convertirlo a lista
            if texto.strip(): 
                datos_actuales = json.loads(texto)
    except Exception as e:
        print(f"Nota: Archivo nuevo o vacío ({e})")
        datos_actuales = []

    # 2. Agregar el nuevo
    datos_actuales.append(nuevo_dato)
    
    # 3. Subir
    nuevo_json = json.dumps(datos_actuales, indent=4)
    nuevo_b64 = base64.b64encode(nuevo_json.encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": "Nuevo registro",
        "content": nuevo_b64,
        "sha": sha
    }
    
    put_resp = requests.put(url, headers=headers, json=payload)
    return put_resp.status_code in [200, 201]

# --- INTERFAZ ---
st.title("🌐 Registro de Inventario")

texto = st.text_area("Movimiento:", placeholder="Ej: Laptop Dell enviada a Quito")

if st.button("Guardar en Nube", type="primary"):
    if texto:
        try:
            client = genai.Client(api_key=API_KEY)
            prompt = f"""Analiza: "{texto}". Devuelve SOLO JSON. Keys: fecha, serie, equipo, accion, ubicacion, reporte."""
            
            resp = client.models.generate_content(model="gemini-flash-latest", contents=prompt)
            
            # Limpieza robusta de la respuesta de la IA
            limpio = resp.text.replace("```json", "").replace("```", "").strip()
            
            if not limpio:
                st.error("La IA devolvió una respuesta vacía. Intenta de nuevo.")
            else:
                info = json.loads(limpio)
                info["fecha"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                info["reporte"] = texto
                
                if guardar_en_github(info):
                    st.success("✅ ¡Guardado! Se procesará al encender tu PC.")
                else:
                    st.error("Error conectando con GitHub (Revisa el Token).")
                    
        except json.JSONDecodeError:
            st.error("Error leyendo la respuesta de la IA (No fue JSON válido).")
            st.write("Respuesta cruda:", limpio)
        except Exception as e:
            st.error(f"Error general: {e}")
