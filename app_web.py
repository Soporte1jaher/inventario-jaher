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
    """Extrae JSON de forma ultra-robusta eliminando markdown y texto extra."""
    try:
        # 1. Limpiar bloques de código Markdown (```json ... ```)
        if "```" in texto:
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
        
        # 2. Buscar el primer [ o { y el último ] o }
        inicio = texto.find("[")
        if inicio == -1: inicio = texto.find("{")
        fin = texto.rfind("]") + 1
        if fin == 0: fin = texto.rfind("}") + 1
        
        if inicio != -1 and fin > inicio:
            return texto[inicio:fin].strip()
        return texto.strip()
    except:
        return ""

# --- INTERFAZ ---
st.title("🤖 LAIA: Inteligencia Logística Pro V5.2")
t1, t2, t3, t4 = st.tabs(["📝 Registro & Estrategia", "💬 Chat IA", "🗑️ Limpieza Inteligente", "📊 Historial"])

# --- TAB 1: REGISTRO & ESTRATEGIA ---
with t1:
    st.subheader("📝 Gestión de Movimientos y Distribución")
    st.info("💡 Tip: Puedes pegar listas de series o pedir repartos: 'Divide 100 mouses para 5 agencias'")
    texto_input = st.text_area("Orden logística:", height=200, placeholder="Ej: llegaron 50 teclados de quito para stock bodega 1...")
    
    if st.button("🚀 Ejecutar Orden", type="primary"):
        if texto_input.strip():
            with st.spinner("LAIA procesando lógica avanzada..."):
                try:
                    client = genai.Client(api_key=API_KEY)
                    prompt = f"""
                    Actúa como un experto en base de datos logísticas.
                    OBJETIVO: Convertir el texto en registros JSON válidos.
                    TEXTO: "{texto_input}"

                    REGLAS CRÍTICAS:
                    1. DESTINO: 'Movimientos' (equipos con serie única) o 'Stock' (periféricos como mouse, teclado, cables).
                    2. REPARTO: Si piden dividir, crea un registro 'Enviado' por cada destino con la cantidad calculada.
                    3. SERIES: Si hay múltiples series, crea un registro por cada una.
                    4. ESTADO: Identifica si es 'Nuevo', 'Usado', 'Dañado' o 'En Reparación'.
                    
                    RESPONDE ÚNICAMENTE CON EL JSON (SIN TEXTO EXPLICATIVO).
                    FORMATO: [{{ "destino": "...", "tipo": "Recibido/Enviado", "cantidad": n, "equipo": "...", "marca": "...", "serie": "...", "estado": "...", "ubicacion": "...", "reporte": "..." }}]
                    """
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                    json_limpio = extraer_json(resp.text)
                    
                    if json_limpio:
                        datos = json.loads(json_limpio)
                        if isinstance(datos, dict): datos = [datos] # Normalizar a lista
                        
                        fecha = obtener_fecha_ecuador()
                        for d in datos: d["fecha"] = fecha
                        
                        if enviar_buzon(datos):
                            st.balloons()
                            st.success(f"✅ LAIA procesó exitosamente {len(datos)} registros.")
                            st.table(pd.DataFrame(datos))
                        else:
                            st.error("❌ Error de comunicación con el repositorio.")
                    else:
                        st.error("❌ LAIA no pudo estructurar los datos. Intenta ser más descriptivo.")
                except Exception as e:
                    st.error(f"❌ Error crítico: {e}")

# --- TAB 2: CHAT IA ---
with t2:
    st.subheader("💬 Consulta Semántica")
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
with t3:
    st.subheader("🗑️ Motor de Limpieza Universal")
    st.warning("⚠️ Esta acción procesa filtros de borrado en todas las columnas.")
    txt_borrar = st.text_area("Criterio de limpieza:", placeholder="Ej: borra las series vacías, borra los recibidos, borra lo que diga 'sin detalle'...")
    
    if st.button("🗑️ EJECUTAR LIMPIEZA CRÍTICA"):
        if txt_borrar.strip():
            with st.spinner("Analizando criterios de borrado..."):
                try:
                    client = genai.Client(api_key=API_KEY)
                    prompt_b = f"""
                    Analiza la orden de borrado: "{txt_borrar}"
                    Clasifica en JSON según corresponda:
                    1. 'borrar_todo': Vacia el inventario.
                    2. 'borrar_vacios': Series 'nan', 'sin serie', o en blanco.
                    3. 'borrar_filtro': Columna y valor exacto (ej. tipo: Recibido).
                    4. 'borrar_contiene': Valor que puede estar en cualquier columna.
                    
                    RESPONDE SOLO JSON:
                    [{{"accion": "...", "columna": "...", "valor": "..."}}]
                    """
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_b)
                    json_limpio = extraer_json(resp.text)
                    
                    if json_limpio:
                        lista_borrar = json.loads(json_limpio)
                        if enviar_buzon(lista_borrar):
                            st.warning("✅ Instrucciones de limpieza enviadas al Sincronizador.")
                            st.json(lista_borrar)
                    else:
                        st.error("❌ No se detectó una orden de borrado clara.")
                except Exception as e:
                    st.error(f"❌ Error en limpieza: {e}")

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
