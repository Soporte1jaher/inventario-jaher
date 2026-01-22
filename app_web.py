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
    st.error("❌ Configura los Secrets.")
    st.stop()

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Cache-Control": "no-cache"}

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
    try:
        i = texto.find("[")
        f = texto.rfind("]") + 1
        if i != -1 and f != 0: return texto[i:f]
        return ""
    except: return ""

st.title("🤖 LAIA: Inteligencia Logística Pro")
t1, t2, t3, t4 = st.tabs(["📝 Registro & Estrategia", "💬 Chat IA", "🗑️ Borrado Masivo", "📊 Historial"])

with t1:
    st.subheader("📝 Gestión de Movimientos y Distribución")
    st.info("Puedes decir: 'Reparte 100 mouses a 10 agencias' o pegar 50 series de golpe.")
    
    texto_input = st.text_area("Orden logística:", height=200, placeholder="Ej: Registra estas series: [Pega 50 series aquí] o 'Divide 50 teclados para 5 agencias'")
    
    if st.button("🚀 Ejecutar Orden", type="primary"):
        if texto_input.strip():
            with st.spinner("LAIA calculando y procesando..."):
                client = genai.Client(api_key=API_KEY)
                prompt = f"""
                Eres una Estratega Logística. Analiza: "{texto_input}"
                TAREAS:
                1. SI HAY MUCHAS SERIES: Crea un objeto JSON por cada serie.
                2. SI HAY DISTRIBUCIÓN (ej. repartir stock): Calcula la división y genera registros 'Enviado' con la cantidad resultante para cada destino.
                3. DESTINO: 'Movimientos' (equipos con serie) o 'Stock' (periféricos/cantidad).
                4. FORMATO: Devuelve una LISTA de objetos JSON.
                JSON: [{{ "destino": "...", "tipo": "Enviado/Recibido", "cantidad": n, "equipo": "...", "marca": "...", "serie": "...", "ubicacion": "...", "reporte": "Cálculo automático LAIA" }}]
                """
                resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                json_limpio = extraer_json(resp.text)
                if json_limpio:
                    datos = json.loads(json_limpio)
                    fecha = obtener_fecha_ecuador()
                    for d in datos: d["fecha"] = fecha
                    if enviar_buzon(datos):
                        st.balloons()
                        st.success(f"✅ LAIA generó {len(datos)} registros.")
                        st.table(pd.DataFrame(datos).head(10))
                else: st.error("LAIA no pudo procesar la lógica de esa orden.")

with t2:
    st.subheader("💬 Consulta Inteligente")
    if p_chat := st.chat_input("Pregunta sobre stock o historial..."):
        hist, _ = obtener_github(FILE_HISTORICO)
        contexto = f"Datos: {json.dumps(hist[-150:])}. Responde pro. Si preguntan stock de mouses/teclados, suma Recibidos y resta Enviados de 'Stock'."
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=contexto + p_chat)
        st.markdown(resp.text)

with t3:
    st.subheader("🗑️ Control de Eliminación")
    txt_borrar = st.text_area("¿Qué quieres eliminar?", placeholder="Ej: 'Elimina todas las series de Manta' o 'Borra la serie 12345'")
    if st.button("🗑️ EJECUTAR BORRADO"):
        client = genai.Client(api_key=API_KEY)
        # LAIA decide si es un borrado selectivo o total
        prompt_b = f"Analiza: '{txt_borrar}'. Si pide borrar TODO, devuelve [{{'accion': 'borrar_todo'}}]. Si son series, extráelas: [{{'serie': '...', 'accion': 'borrar'}}]"
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_b)
        lista_borrar = json.loads(extraer_json(resp.text))
        if enviar_buzon(lista_borrar):
            st.warning("✅ Orden de borrado enviada al sincronizador.")

with t4:
    if st.button("🔄 Cargar Historial"):
        datos, _ = obtener_github(FILE_HISTORICO)
        if datos: st.dataframe(pd.DataFrame(datos), use_container_width=True)
