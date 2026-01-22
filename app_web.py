import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="LAIA INTELLIGENCE V2", page_icon="🧠", layout="wide")

# --- CREDENCIALES (Asegúrate de tenerlas en secrets) ---
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
HEADERS = {"Authorization": f"token {}", "Cache-Control": "no-cache"}

def obtener_fecha_ecuador():
    return (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")

def obtener_github(archivo):
    url = f"https://api.github.com/repos/{}/{}/contents/{}"
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
        "message": "LAIA LOGIC UPDATE",
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha
    }
    url = f"https://api.github.com/repos/{}/{}/contents/{}"
    return requests.put(url, headers=HEADERS, json=payload).status_code in [200, 201]

def extraer_json(texto):
    try:
        if "```" in texto:
            texto = texto.split("```")[1]
            if texto.startswith("json"): texto = texto[4:]
        inicio = texto.find("[")
        if inicio == -1: inicio = texto.find("{")
        fin = texto.rfind("]") + 1
        if fin == 0: fin = texto.rfind("}") + 1
        return texto[inicio:fin].strip()
    except: return ""

# --- INTERFAZ ---
st.title("🤖 LAIA INTELLIGENCE V2")
t1, t2, t3, t4 = st.tabs(["📝 Registro Inteligente", "💬 Consultas", "🗑️ Borrado Semántico", "📊 Historial"])

# --- TAB 1: REGISTRO (CON LOGICA DE NEGOCIO) ---
with t1:
    st.subheader("📝 Gestión de Inventario")
    texto_input = st.text_area("¿Qué llegó o se envió?", placeholder="Ej: Envié 3 mouses nuevos a Manta y recibí el CPU de Ambato dañado...")
    
    if st.button("🚀 Procesar con IA"):
        with st.spinner("Analizando semántica logística..."):
            client = genai.Client(api_key=API_KEY)
            prompt = f"""
            Eres un experto en logística. Tu tarea es extraer registros del siguiente texto: "{}".
            REGLAS:
            - Si el texto dice 'envié', el tipo es 'Enviado'. Si dice 'llegó' o 'recibí', es 'Recibido'.
            - Identifica marcas, series y estados (Nuevo, Usado, Dañado).
            - Si mencionan una ciudad, ponla en 'ubicacion'.
            - Si piden repartir (ej. 10 para 2 agencias), crea registros separados.
            - FORMATO JSON: [{{"destino": "Movimientos/Stock", "tipo": "Recibido/Enviado", "cantidad": 1, "equipo": "", "marca": "", "serie": "", "estado": "", "ubicacion": "", "reporte": ""}}]
            RESPONDE SOLO EL JSON.
            """
            resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
            json_limpio = extraer_json(resp.text)
            if json_limpio:
                datos = json.loads(json_limpio)
                fecha = obtener_fecha_ecuador()
                for d in datos: d["fecha"] = fecha
                if enviar_buzon(datos):
                    st.success("✅ Registros procesados")
                    st.table(pd.DataFrame(datos))


# --- TAB 2: CHAT IA ---
with t2:
    st.subheader("💬 Consulta Inventario")
    if "messages" not in st.session_state: st.session_state.messages = []
    
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p_chat := st.chat_input("¿Cuántos mouses quedan?"):
        st.session_state.messages.append({"role": "user", "content": p_chat})
        with st.chat_message("user"): st.markdown(p_chat)
        
        hist, _ = obtener_github(FILE_HISTORICO)
        contexto = f"Datos actuales: {json.dumps(hist[-150:])}. Responde de forma breve y profesional."
        
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=contexto + p_chat)
        
        with st.chat_message("assistant"): st.markdown(resp.text)
        st.session_state.messages.append({"role": "assistant", "content": resp.text})

# --- TAB 3: LIMPIEZA INTELIGENTE ---
TAB 3: EL BORRADO "INTELIGENTE" (AQUÍ ESTÁ EL CAMBIO) ---
with t3:
    st.subheader("🗑️ Motor de Borrado Semántico")
    st.info("Ahora puedes decir: 'Borra el CPU que mandamos a Ambato ayer'")
    txt_borrar = st.text_input("¿Qué registro deseas eliminar?")
    
    if st.button("🗑️ IDENTIFICAR Y ELIMINAR"):
        if txt_borrar:
            with st.spinner("Buscando coincidencias en el inventario..."):
                # PASO 1: Obtener los datos actuales para darle memoria a la IA
                inventario_actual, _ = obtener_github(FILE_HISTORICO)
                # Solo mandamos los últimos 100 para no saturar el token, pero con campos clave
                contexto_data = json.dumps(inventario_actual[-100:]) 

                client = genai.Client(api_key=API_KEY)
                prompt_b = f"""
                CONTEXTO DE DATOS ACTUALES: {contexto_data}
                ORDEN DEL USUARIO: "{}"
                
                TAREA:
                1. Analiza los datos actuales y encuentra el o los registros que coinciden con la orden del usuario.
                2. Si el usuario dice "el CPU de Ambato", busca en el contexto qué registro tiene equipo="CPU" y ubicacion="Ambato".
                3. Devuelve una instrucción de borrado precisa usando la 'serie' o un 'filtro_multiple'.

                FORMATO DE RESPUESTA JSON:
                [
                  {{"accion": "borrar_filtro_multiple", "criterios": {{"serie": "XYZ123", "equipo": "CPU"}}}}
                ]
                """
                resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_b)
                instruccion = extraer_json(resp.text)
                
                if instruccion:
                    inst_json = json.loads(instruccion)
                    if enviar_buzon(inst_json):
                        st.warning(f"✅ LAIA identificó el registro y envió la orden de eliminación.")
                        st.json(inst_json)
                else:
                    st.error("No pude identificar qué registro quieres borrar. Sé más específico.")

# --- TAB 4: HISTORIAL ---
with t4:
    if st.button("🔄 Cargar Historial Completo"):
        with st.spinner("Obteniendo datos..."):
            datos, _ = obtener_github(FILE_HISTORICO)
            if datos:
                df = pd.DataFrame(datos)
                # Reordenar para que sea legible
                cols = ["fecha", "tipo", "cantidad", "estado", "equipo", "marca", "serie", "ubicacion", "reporte"]
                df = df.reindex(columns=[c for c in cols if c in df.columns])
                st.dataframe(df, use_container_width=True)
            else:
                st.info("El inventario está vacío.")
