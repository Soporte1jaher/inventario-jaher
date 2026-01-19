import streamlit as st
from google import genai
import json
import requests
import base64
import datetime

st.set_page_config(page_title="Inventario Web", page_icon="🌐")

# --- CREDENCIALES ---
# Tu clave de Google (pon la tuya real aquí)
API_KEY = 'AIzaSyAq2dk2s7V61xuusl3WvzjKqbKBdkFTs9k'

# --- DATOS GITHUB YA RELLENOS ---
GITHUB_TOKEN = "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"
GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
GITHUB_FILE = "buzon.json" 

def guardar_en_github(nuevo_dato):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    # 1. Bajar lo que ya existe para no borrarlo
    datos_actuales = []
    sha = None
    
    # Intentamos leer si ya existe el archivo
    resp = requests.get(url, headers=headers)
    
    if resp.status_code == 200:
        content = resp.json()
        sha = content['sha']
        try:
            texto = base64.b64decode(content['content']).decode('utf-8')
            if texto: datos_actuales = json.loads(texto)
        except:
            pass # Si falla o esta vacio, iniciamos lista nueva

    # 2. Agregar el nuevo registro a la lista
    datos_actuales.append(nuevo_dato)
    
    # 3. Subir la lista actualizada
    nuevo_json_str = json.dumps(datos_actuales, indent=4)
    nuevo_b64 = base64.b64encode(nuevo_json_str.encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": "Nuevo registro desde Web",
        "content": nuevo_b64,
        "sha": sha # Si sha es None, crea archivo nuevo. Si tiene valor, actualiza.
    }
    
    put_resp = requests.put(url, headers=headers, json=payload)
    return put_resp.status_code in [200, 201]

# --- INTERFAZ ---
st.title("🌐 Registro de Inventario (Nube)")
st.caption("Los datos se guardan en GitHub hasta que prendas tu PC.")

texto = st.text_area("Movimiento:", placeholder="Ej: Laptop Dell serie 123 enviada a Quito")

if st.button("Guardar en Nube", type="primary"):
    if texto:
        try:
            client = genai.Client(api_key=API_KEY)
            prompt = f"""Analiza: "{texto}". JSON keys: fecha, serie, equipo, accion, ubicacion, reporte."""
            resp = client.models.generate_content(model="gemini-flash-latest", contents=prompt)
            
            # Limpieza del JSON
            limpio = resp.text.replace("```json","").replace("```","").strip()
            info = json.loads(limpio)
            
            # Completamos datos
            info["fecha"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            info["reporte"] = texto
            
            # Guardamos
            if guardar_en_github(info):
                st.success("✅ Guardado Exitosamente en la Nube.")
                st.info("Tu computadora descargará este dato cuando la enciendas.")
            else:
                st.error("Error conectando con GitHub.")
                
        except Exception as e:
            st.error(f"Error: {e}")
