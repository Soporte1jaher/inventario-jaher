import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd
import re

# --- CONFIGURACIÓN DE PÁGINA (ESTÉTICA MAMADA) ---
st.set_page_config(page_title="LAIA NEURAL SYSTEM", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2e7d32; color: white; border: none; }
    .stTextArea>div>div>textarea { background-color: #1a1c23; color: #00ff00; font-family: 'Courier New', monospace; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
</style>
""", unsafe_allow_html=True)

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
    except Exception as e:
        pass
    return [], None

def enviar_buzon(datos):
    if not isinstance(datos, list): datos = [datos]
    actuales, sha = obtener_github(FILE_BUZON)
    actuales.extend(datos)
    payload = {
        "message": "LAIA NEURAL UPDATE",
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha
    }
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_BUZON}"
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
        if inicio != -1 and fin > inicio:
            return texto[inicio:fin].strip()
        return texto.strip()
    except: return ""

# --- MOTOR MATEMÁTICO WEB (Calcula Stock Real: Entradas - Salidas) ---
def calcular_stock_tiempo_real(df):
    if df.empty: return pd.DataFrame()
    
    df_c = df.copy()
    
    # 1. Normalización para que coincidan (Mouse N/A == Mouse Genérica)
    for col in ['marca', 'estado', 'serie', 'tipo', 'destino', 'equipo']:
        if col not in df_c.columns: df_c[col] = "N/A"
        df_c[col] = df_c[col].astype(str).str.strip()
    
    # Unificamos marcas y estados nulos
    df_c['marca'] = df_c['marca'].replace(['N/A', 'n/a', 'None', '', 'nan'], 'Genérica')
    df_c['estado'] = df_c['estado'].replace(['N/A', 'n/a', 'None', '', 'nan'], 'Nuevo')
    df_c['cantidad'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(1)
    
    # 2. Lógica Matemática (+/-)
    def flujo(row):
        tipo = row['tipo'].lower()
        dest = row['destino'].lower()
        ser = row['serie'].lower()
        cant = row['cantidad']
        
        # Si es activo único (tiene serie larga), NO lo sumamos al bulto
        es_activo = len(ser) > 3 and "n/a" not in ser and "sin serie" not in ser
        if es_activo: return 0
        
        # Sumar entradas a stock
        if dest == 'stock': return cant
        
        # Restar salidas de stock
        if 'enviado' in tipo or 'salida' in tipo: return -cant
        
        return 0

    df_c['val'] = df_c.apply(flujo, axis=1)
    
    # 3. Agrupar y Filtrar
    stock = df_c.groupby(['equipo', 'marca'])['val'].sum().reset_index()
    stock = stock[stock['val'] > 0] # Solo mostrar stock positivo
    stock.columns = ['Equipo', 'Marca', 'Cantidad']
    return stock

# --- INTERFAZ ---
st.title("🤖 LAIA NEURAL ENGINE v11.0")
t1, t2, t3, t4 = st.tabs(["📝 Registro Inteligente", "💬 Chat Consultor", "🗑️ Limpieza Quirúrgica", "📊 BI & Historial"])

# --- TAB 1: REGISTRO ---
with t1:
    st.subheader("📝 Gestión de Movimientos")
    st.info("💡 IA V11: Clasificación Estricta y Corrección de Datos.")
    texto_input = st.text_area("Orden Logística:", height=200, placeholder="Ej: Envié un CPU a Manta. O me llegaron 20 mouses para stock...")
    
    if st.button("🚀 EJECUTAR ACCIÓN INTELIGENTE", type="primary"):
        if texto_input.strip():
            with st.spinner("LAIA procesando lógica de inventario..."):
                try:
                    client = genai.Client(api_key=API_KEY)
                    prompt = f"""
                    Actúa como un Auditor Logístico. TEXTO: "{texto_input}"
                    REGLAS DE ORO:
                    1. TIPO: Solo "Recibido" (Entradas) o "Enviado" (Salidas).
                    2. ESTADO: "Dañado" (Falla técnica), "Usado" (Estético), "Nuevo".
                    3. STOCK: Si es "a stock" o consumibles masivos -> Destino: "Stock".
                    4. MATH: 
                       - "20 mouses a stock" -> 1 fila, cantidad 20.
                       - "Laptop con cargador" -> 1 fila Laptop, cargador en 'reporte'.
                    5. CORRECCIÓN: "cragador"->"Cargador". Marca "N/A" si no existe -> "Genérica".

                    JSON: [{{ "destino": "...", "tipo": "Recibido/Enviado", "cantidad": 1, "equipo": "...", "marca": "...", "serie": "...", "estado": "...", "ubicacion": "...", "reporte": "..." }}]
                    """
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                    json_limpio = extraer_json(resp.text)
                    
                    if json_limpio:
                        datos = json.loads(json_limpio)
                        fecha = obtener_fecha_ecuador()
                        
                        for d in datos: 
                            d["fecha"] = fecha
                            # Corrección forzada de seguridad
                            tipo = str(d.get("tipo", "")).lower()
                            if "env" in tipo: d["tipo"] = "Enviado"
                            elif "rec" in tipo or "stock" in str(d.get("destino","")).lower(): d["tipo"] = "Recibido"

                        if enviar_buzon(datos):
                            st.success(f"✅ Procesado: {len(datos)} registros.")
                            st.table(pd.DataFrame(datos))
                        else: st.error("Error GitHub")
                except Exception as e: st.error(f"Error IA: {e}")

# --- TAB 2: CHAT IA (CON CEREBRO MATEMÁTICO + RESET) ---
with t2:
    # Cabecera con botón de reset
    col_c1, col_c2 = st.columns([4, 1])
    col_c1.subheader("💬 Consulta de Stock Real")
    if col_c2.button("🧹 Nueva Conversación"):
        st.session_state.messages = []
        st.rerun()

    if "messages" not in st.session_state: st.session_state.messages = []
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p_chat := st.chat_input("¿Cuántos mouses quedan?"):
        st.session_state.messages.append({"role": "user", "content": p_chat})
        with st.chat_message("user"): st.markdown(p_chat)
        
        # OBTENEMOS DATOS Y CALCULAMOS STOCK ANTES DE DARSELO A LA IA
        hist, _ = obtener_github(FILE_HISTORICO)
        df_hist = pd.DataFrame(hist)
        
        # Calculamos el saldo real (Matemática V11)
        df_saldo = calcular_stock_tiempo_real(df_hist)
        
        # Contexto Enriquecido
        contexto = f"""
        ERES EL GESTOR DE INVENTARIO "LAIA".
        
        1. STOCK REAL (Saldos calculados Entradas-Salidas):
        {df_saldo.to_string(index=False) if not df_saldo.empty else "Bodega Vacía"}
        
        2. HISTORIAL COMPLETO (Referencia):
        {json.dumps(hist[-50:])}
        
        PREGUNTA DEL USUARIO: "{p_chat}"
        Responde basándote PRINCIPALMENTE en la tabla de STOCK REAL para cantidades.
        """
        
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=contexto)
        
        with st.chat_message("assistant"): st.markdown(resp.text)
        st.session_state.messages.append({"role": "assistant", "content": resp.text})

# --- TAB 3: LIMPIEZA ---
with t3:
    st.subheader("🗑️ Corrección de Registros")
    txt_borrar = st.text_input("Describe qué borrar:")
    if st.button("🔥 EJECUTAR BORRADO DE PRECISIÓN"):
        if txt_borrar:
            hist, _ = obtener_github(FILE_HISTORICO)
            client = genai.Client(api_key=API_KEY)
            prompt_b = f"DATA: {json.dumps(hist[-100:])}. USER WANTS TO DELETE: '{txt_borrar}'. RETURN JSON: [{{'accion':'borrar_quirurgico', 'serie':'...', 'equipo':'...'}}]"
            resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_b)
            orden = extraer_json(resp.text)
            if orden and enviar_buzon(json.loads(orden)): 
                st.success("Orden enviada.")
                st.json(orden)

# --- TAB 4: BI & DASHBOARD (CALCULADO) ---
with t4:
    c1, c2 = st.columns([3,1])
    c1.subheader("📊 Dashboard en Tiempo Real")
    if c2.button("🔄 Recalcular Dashboard"): st.rerun()

    datos, _ = obtener_github(FILE_HISTORICO)
    if datos:
        df = pd.DataFrame(datos)
        
        # --- CÁLCULO DE STOCK EN TIEMPO REAL ---
        df_stock_real = calcular_stock_tiempo_real(df)
        
        # Métricas
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📦 Items Diferentes en Stock", len(df_stock_real))
        col2.metric("🔢 Unidades Totales (Suma)", int(df_stock_real['Cantidad'].sum()) if not df_stock_real.empty else 0)
        
        # Conteo KPIs
        if 'tipo' in df.columns:
            cant_env = len(df[df['tipo'].astype(str).str.lower().str.contains('enviado')])
            cant_rec = len(df[df['tipo'].astype(str).str.lower().str.contains('recibido')])
            col3.metric("📤 Enviados", cant_env, delta="Salidas", delta_color="off")
            col4.metric("📥 Recibidos", cant_rec, delta="Entradas")
        
        st.divider()
        
        # Sub-Pestañas
        t_stock, t_movs, t_bad, t_audit = st.tabs(["📦 STOCK REAL (Saldos)", "🚚 Historial Movimientos", "⚠️ Reporte Dañados", "🕵️ Auditoría"])
        
        # 1. STOCK REAL
        with t_stock:
            if not df_stock_real.empty:
                st.dataframe(df_stock_real, use_container_width=True, hide_index=True)
            else:
                st.warning("El stock calculado está vacío.")
        
        # 2. HISTORIAL
        with t_movs:
            if 'tipo' in df.columns:
                filtro = st.radio("Ver:", ["Todos", "Enviados", "Recibidos"], horizontal=True)
                if filtro == "Enviados":
                    st.dataframe(df[df['tipo'].astype(str).str.lower().str.contains('env')], use_container_width=True)
                elif filtro == "Recibidos":
                    st.dataframe(df[df['tipo'].astype(str).str.lower().str.contains('rec')], use_container_width=True)
                else:
                    st.dataframe(df, use_container_width=True)
            else:
                st.dataframe(df, use_container_width=True)
            
        # 3. DAÑADOS
        with t_bad:
            if 'estado' in df.columns:
                df_bad = df[df['estado'].astype(str).str.lower().str.contains('dañ')]
                if not df_bad.empty:
                    cols = list(df_bad.columns)
                    if 'reporte' in cols: cols.insert(0, cols.pop(cols.index('reporte')))
                    st.dataframe(df_bad[cols], use_container_width=True)
                else:
                    st.success("No hay equipos dañados reportados.")

        # 4. AUDITORÍA (Detector de Doble Salida)
        with t_audit:
            st.info("Detectando series enviadas dos veces sin reingreso...")
            series_problem = []
            if 'serie' in df.columns and 'tipo' in df.columns:
                df_ser = df[df['serie'].astype(str).str.len() > 3].copy() 
                for ser, group in df_ser.groupby('serie'):
                    if len(group) > 1:
                        tipos = group['tipo'].astype(str).str.lower().tolist()
                        for i in range(len(tipos) - 1):
                            if 'env' in tipos[i] and 'env' in tipos[i+1]:
                                series_problem.append({"Serie": ser, "Equipo": group.iloc[0].get('equipo'), "Alerta": "Doble Salida Consecutiva"})
                                break
            
            if series_problem:
                st.dataframe(pd.DataFrame(series_problem), use_container_width=True)
            else:
                st.success("✅ Lógica consistente.")

    else:
        st.warning("Sin datos.")
