import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="LAIA Intelligence PRO", page_icon="🤖", layout="wide")

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
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Cache-Control": "no-cache"}

# --- FUNCIONES DE APOYO ---
def obtener_fecha_ecuador():
    return (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")

def obtener_github(archivo):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}"
    try:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 200:
            d = resp.json()
            return json.loads(base64.b64decode(d['content']).decode('utf-8')), d['sha']
    except: pass
    return [], None

def enviar_buzon(datos):
    if not isinstance(datos, list): datos = [datos]
    actuales, sha = obtener_github(FILE_BUZON)
    actuales.extend(datos)
    payload = {
        "message": "LAIA STRATEGIC UPDATE",
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha
    }
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_BUZON}"
    return requests.put(url, headers=HEADERS, json=payload).status_code in [200, 201]

def extraer_json(texto):
    """Extrae de forma robusta el JSON del texto de la IA"""
    try:
        # Busca el inicio y fin de una lista [] o un objeto {}
        inicio = texto.find("[")
        if inicio == -1: inicio = texto.find("{")
        fin = texto.rfind("]") + 1
        if fin == 0: fin = texto.rfind("}") + 1
        
        if inicio != -1 and fin != 0:
            return texto[inicio:fin]
        return ""
    except:
        return ""

# --- INTERFAZ ---
st.title("🤖 LAIA: Inteligencia Logística Pro V5.1")
t1, t2, t3, t4 = st.tabs(["📝 Registro & Estrategia", "💬 Chat IA", "🗑️ Limpieza Inteligente", "📊 Historial"])

# --- TAB 1: REGISTRO ---
with t1:
    st.subheader("📝 Gestión de Movimientos y Distribución")
    texto_input = st.text_area("Orden logística:", height=200, placeholder="Ej: reparte 100 mouses a 10 agencias...")
    
    if st.button("🚀 Ejecutar Orden", type="primary"):
        if texto_input.strip():
            with st.spinner("LAIA calculando logística..."):
                try:
                    client = genai.Client(api_key=API_KEY)
                    prompt = f"""
                    Analiza: "{texto_input}"
                    1. SI HAY MUCHAS SERIES: Genera un registro por cada una.
                    2. SI HAY REPARTO: Calcula y genera registros 'Enviado'.
                    3. DESTINO: 'Movimientos' (serie) o 'Stock' (periféricos).
                    FORMATO JSON: [{{ "destino": "...", "tipo": "Enviado/Recibido", "cantidad": n, "equipo": "...", "marca": "...", "serie": "...", "ubicacion": "...", "reporte": "Procesado por LAIA" }}]
                    """
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                    json_limpio = extraer_json(resp.text)
                    
                    if json_limpio:
                        datos = json.loads(json_limpio)
                        fecha = obtener_fecha_ecuador()
                        for d in datos: d["fecha"] = fecha
                        if enviar_buzon(datos):
                            st.success(f"✅ LAIA procesó {len(datos)} registros.")
                            st.table(pd.DataFrame(datos).head(10))
                    else:
                        st.error("❌ LAIA no pudo generar los datos. Intenta ser más claro.")
                except Exception as e:
                    st.error(f"❌ Error al procesar JSON: {e}")

# --- TAB 2: CHAT IA ---
with t2:
    st.subheader("💬 Consulta Semántica")
    if p_chat := st.chat_input("¿Qué deseas consultar?"):
        hist, _ = obtener_github(FILE_HISTORICO)
        contexto = f"Datos: {json.dumps(hist[-100:])}. Responde pro."
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=contexto + p_chat)
        st.markdown(resp.text)

# --- TAB 3: LIMPIEZA ---
with t3:
    st.subheader("🗑️ Motor de Limpieza Universal")
    txt_borrar = st.text_area("Orden de limpieza:", placeholder="Ej: borra todos los Recibidos...")
    
    if st.button("🗑️ EJECUTAR LIMPIEZA"):
        if txt_borrar.strip():
            with st.spinner("Analizando orden..."):
                try:
                    client = genai.Client(api_key=API_KEY)
                    prompt_b = f"""
                    Analiza la orden: "{txt_borrar}"
                    JSON: [{{ "accion": "borrar_filtro/borrar_vacios/borrar_contiene/borrar_todo", "columna": "nombre", "valor": "valor" }}]
                    """
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_b)
                    json_limpio = extraer_json(resp.text)
                    
                    if json_limpio:
                        lista_borrar = json.loads(json_limpio)
                        if enviar_buzon(lista_borrar):
                            st.warning("⚠️ Orden enviada al sistema.")
                            st.json(lista_borrar)
                    else:
                        st.error("❌ LAIA no entendió qué borrar.")
                except Exception as e:
                    st.error(f"❌ Error en limpieza: {e}")

# --- TAB 4: HISTORIAL ---
with t4:
    if st.button("🔄 Cargar Historial"):
        datos, _ = obtener_github(FILE_HISTORICO)
        if datos: st.dataframe(pd.DataFrame(datos), use_container_width=True)
