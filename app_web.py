import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd
import re

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA
# ==========================================
st.set_page_config(page_title="LAIA NEURAL SYSTEM", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2e7d32; color: white; border: none; }
    .stTextArea>div>div>textarea { background-color: #1a1c23; color: #00ff00; font-family: 'Courier New', monospace; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CREDENCIALES
# ==========================================
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

# ==========================================
# 3. FUNCIONES DE APOYO
# ==========================================
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

# ==========================================
# 4. MOTOR MATEMÁTICO (CORREGIDO PARA CABLES Y STOCK)
# ==========================================
def calcular_stock_web(df):
    if df.empty: return pd.DataFrame()
    df_c = df.copy()
    
    # 1. Normalizar nombres de columnas (Arregla "Cant" vs "cantidad")
    df_c.columns = df_c.columns.str.lower().str.strip()
    mapa_cols = {'cant': 'cantidad', 'condición': 'estado', 'condicion': 'estado', 'equipos': 'equipo'}
    df_c = df_c.rename(columns=mapa_cols)

    # 2. Rellenar vacíos y forzar texto
    for col in ['marca', 'estado', 'serie', 'tipo', 'destino', 'equipo']:
        if col not in df_c.columns: df_c[col] = "N/A"
        df_c[col] = df_c[col].astype(str).str.strip()
    
    # 3. UNIFICAR "None" -> "Genérica" (ESTO ARREGLA LA RESTA)
    valores_nulos = ['n/a', 'none', 'nan', 'null', '', 'sin marca', 'genérica', 'generica', 'desconocida']
    df_c['marca'] = df_c['marca'].str.lower().replace(valores_nulos, 'genérica')
    df_c['estado'] = df_c['estado'].str.lower().replace(valores_nulos, 'nuevo') # O 'bueno'
    
    # 4. Asegurar números
    if 'cantidad' not in df_c.columns: df_c['cantidad'] = 1
    df_c['cantidad'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(1)
    
    # 5. Lógica (+/-)
    def flujo(row):
        tipo = str(row['tipo']).lower()
        dest = str(row['destino']).lower()
        ser = str(row['serie']).lower()
        cant = row['cantidad']
        
        # Si es activo único (serie larga), no suma al bulto
        es_activo = len(ser) > 3 and not any(x in ser for x in ['n/a', 'none', 'sin', 'genérica'])
        if es_activo: return 0
        
        if dest == 'stock': return cant # Entrada
        if 'enviado' in tipo or 'salida' in tipo: return -cant # Salida
        return 0

    df_c['val'] = df_c.apply(flujo, axis=1)
    
    # 6. Agrupar
    df_c['equipo'] = df_c['equipo'].str.capitalize()
    df_c['marca'] = df_c['marca'].str.capitalize()
    stock = df_c.groupby(['equipo', 'marca'])['val'].sum().reset_index()
    stock.columns = ['Equipo', 'Marca', 'Stock_Disponible']
    
    return stock[stock['Stock_Disponible'] > 0]

# ==========================================
# 5. INTERFAZ
# ==========================================
st.title("🤖 LAIA NEURAL ENGINE v21.0 FINAL")
t1, t2, t3, t4 = st.tabs(["📝 Registro Inteligente", "💬 Chat Consultor", "🗑️ Limpieza Quirúrgica", "📊 BI & Historial"])

# --- TAB 1: REGISTRO (LÓGICA V16.5: DIRECCIONAMIENTO INTELIGENTE) ---
with t1:
    st.subheader("📝 Gestión de Movimientos")
    st.info("💡 IA V16.5: Detecta si 'de stock' es origen (Resta) o destino (Suma).")
    texto_input = st.text_area("Orden Logística:", height=200, placeholder="Ej: Envié mouse a Paute... (Resta) / Recibí mouse a Stock... (Suma)")
    
    if st.button("🚀 EJECUTAR ACCIÓN INTELIGENTE", type="primary"):
        if texto_input.strip():
            with st.spinner("LAIA analizando flujo de inventario..."):
                try:
                    client = genai.Client(api_key=API_KEY)
                    
                    # PROMPT DE LÓGICA LOGÍSTICA
                    prompt = f"""
                    Actúa como un Gerente de Logística Experto. TEXTO: "{texto_input}"
                    
                    TU MISIÓN: Determinar si el inventario SUMA o RESTA.

                    REGLAS DE ORO:
                    1. SALIDAS (RESTA):
                       - Palabras clave: "Envié", "Salida", "Despacho", "Mandar a", "Salió".
                       - Si dice "de stock", significa que SALE de la bodega.
                       - ACCIÓN: TIPO="Enviado". DESTINO="[Ciudad/Lugar]". (NUNCA pongas 'Stock' en destino si es salida).

                    2. ENTRADAS (SUMA):
                       - Palabras clave: "Recibí", "Llegó", "Ingreso", "A stock", "Devolución".
                       - ACCIÓN: TIPO="Recibido". DESTINO="Stock".

                    3. PROCESAMIENTO:
                       - "20 mouses" -> cantidad: 20.
                       - "Laptop con cargador" -> Cargador va en 'reporte', NO fila nueva.
                       - "cragador" -> "Cargador".

                    JSON: [{{ "destino": "...", "tipo": "Recibido/Enviado", "cantidad": 1, "equipo": "...", "marca": "...", "serie": "...", "estado": "...", "ubicacion": "...", "reporte": "..." }}]
                    """
                    
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                    json_limpio = extraer_json(resp.text)
                    
                    if json_limpio:
                        datos = json.loads(json_limpio)
                        fecha = obtener_fecha_ecuador()
                        
                        for d in datos: 
                            d["fecha"] = fecha
                            
                            # --- SEGURIDAD PYTHON (LÓGICA BLINDADA) ---
                            tipo_ia = str(d.get("tipo", "")).lower()
                            dest_ia = str(d.get("destino", "")).lower()
                            
                            # REGLA 1: Si es salida explícita, se respeta como ENVIADO (Resta)
                            if any(x in tipo_ia for x in ["env", "sal", "desp"]):
                                d["tipo"] = "Enviado"
                                # Si la IA se equivocó y puso destino stock en una salida, lo corregimos
                                if "stock" in dest_ia: d["destino"] = "Destino Externo"
                            
                            # REGLA 2: Si es entrada explícita o destino stock, es RECIBIDO (Suma)
                            elif any(x in tipo_ia for x in ["rec", "lleg", "ing"]) or "stock" in dest_ia:
                                d["tipo"] = "Recibido"
                                d["destino"] = "Stock"
                            
                            # REGLA 3: Corrección de Estado
                            est = str(d.get("estado", "")).lower()
                            if "dañ" in est or "rot" in est: d["estado"] = "Dañado"

                        if enviar_buzon(datos):
                            st.success(f"✅ Procesado: {len(datos)} registros.")
                            if any(d.get('estado') == 'Dañado' for d in datos):
                                st.warning("⚠️ Se detectaron equipos DAÑADOS.")
                            st.table(pd.DataFrame(datos))
                        else: st.error("Error GitHub")
                except Exception as e: st.error(f"Error IA: {e}")

# --- TAB 2: CHAT (MATEMÁTICO + RESET) ---
with t2:
    c1, c2 = st.columns([4, 1])
    with c1: st.subheader("💬 Consulta Inteligente")
    with c2: 
        if st.button("🧹 Limpiar"):
            st.session_state.messages = []
            st.rerun()

    if "messages" not in st.session_state: st.session_state.messages = []
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p_chat := st.chat_input("Consulta tu stock..."):
        st.session_state.messages.append({"role": "user", "content": p_chat})
        with st.chat_message("user"): st.markdown(p_chat)
        
        hist, _ = obtener_github(FILE_HISTORICO)
        # Calculamos Stock Real para dárselo a la IA (ESTO ES LO QUE HACE QUE LA RESPUESTA SEA CORRECTA)
        df_real = calcular_stock_web(pd.DataFrame(hist))
        
        contexto = f"""
        INVENTARIO DISPONIBLE (Saldos Calculados):
        {df_real.to_string(index=False) if not df_real.empty else "Bodega Vacía"}
        
        HISTORIAL COMPLETO: {json.dumps(hist[-50:])}
        USUARIO: {p_chat}
        """
        
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=contexto)
        
        with st.chat_message("assistant"): st.markdown(resp.text)
        st.session_state.messages.append({"role": "assistant", "content": resp.text})

# --- TAB 3: LIMPIEZA BLINDADA ---
with t3:
    st.subheader("🗑️ Eliminación y Limpieza")
    st.info("💡 IA V20: Entiende comandos globales.")
    txt_borrar = st.text_input("Orden de eliminación:", placeholder="Ej: 'Borrar todo', 'Limpiar vacíos'")
    
    if st.button("🔥 EJECUTAR BORRADO", type="primary"):
        if txt_borrar:
            with st.spinner("LAIA analizando intención de borrado..."):
                try:
                    hist, _ = obtener_github(FILE_HISTORICO)
                    client = genai.Client(api_key=API_KEY)
                    
                    # Prompt de limpieza
                    prompt_b = f"""
                    Actúa como DBA. DATOS: {json.dumps(hist[-20:])}. ORDEN: "{txt_borrar}"
                    JSON RESPUESTA:
                    1. BORRADO TOTAL -> {{"accion": "borrar_todo"}}
                    2. LIMPIEZA -> {{"accion": "borrar_vacios"}}
                    3. ESPECÍFICO -> {{"accion": "borrar", "serie": "..."}}
                    """
                    
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_b)
                    orden_json = extraer_json(resp.text)
                    
                    if orden_json:
                        data_borrado = json.loads(orden_json)
                        if enviar_buzon(data_borrado):
                            st.success("✅ Orden enviada.")
                            st.json(data_borrado)
                        else:
                            st.error("Error conectando con GitHub.")
                    else:
                        st.warning("Orden no reconocida.")
                        
                except json.JSONDecodeError:
                    st.error("⚠️ Error de formato JSON.")
                except Exception as e:
                    st.error(f"Error inesperado: {e}")

# --- TAB 4: DASHBOARD (ESTRUCTURA ORIGINAL CON NÚMEROS CORREGIDOS) ---

with t4:
    c_head1, c_head2 = st.columns([3, 1])
    c_head1.subheader("📊 Dashboard de Control de Activos")
    if c_head2.button("🔄 Actualizar Datos"): st.rerun()

    datos, _ = obtener_github(FILE_HISTORICO)
    if datos:
        df = pd.DataFrame(datos)
        
        # 1. Calculamos el Stock igual que en el Excel
        df_stock_real = calcular_stock_web(df)
        df_bad = pd.DataFrame()
        if 'estado' in df.columns:
            df_bad = df[df['estado'].astype(str).str.lower().str.contains('dañ')].copy()
        
        # 2. KPIs (Aquí buscamos 'Stock_Disponible', así que ya no dará error)
        total_items = 0
        if not df_stock_real.empty:
            total_items = int(df_stock_real['Stock_Disponible'].sum())
            
        if 'tipo' in df.columns:
            cant_env = len(df[df['tipo'].astype(str).str.lower().str.contains('enviado')])
            cant_rec = len(df[df['tipo'].astype(str).str.lower().str.contains('recibido')])
        else:
            cant_env, cant_rec = 0, 0
            
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("⚠️ Dañados", len(df_bad), delta="Prioridad", delta_color="inverse")
        kpi2.metric("📦 Stock Disp.", total_items)
        kpi3.metric("📤 Enviados", cant_env, delta_color="off")
        kpi4.metric("📥 Recibidos", cant_rec)
        
        st.divider()

        # 3. PESTAÑAS (ORDEN SOLICITADO: Dañados -> Stock -> Movimientos -> Gráficas)
        t_bad, t_stock, t_mov, t_graf = st.tabs(["⚠️ Equipos Dañados", "📦 Stock (Saldos)", "🚚 Enviados/Recibidos", "📊 Gráficas"])
        
        # PESTAÑA 1: DAÑADOS
        with t_bad:
            if not df_bad.empty:
                st.error(f"🚨 {len(df_bad)} equipos dañados.")
                cols = list(df_bad.columns)
                if 'reporte' in cols: cols.insert(0, cols.pop(cols.index('reporte')))
                st.dataframe(df_bad[cols], use_container_width=True)
            else:
                st.success("Sin equipos dañados.")

        # PESTAÑA 2: STOCK (LA TABLA RESUMIDA)
        with t_stock:
            st.info("Inventario Real Disponible (Calculado).")
            if not df_stock_real.empty:
                # Mostramos la tabla limpia
                st.dataframe(df_stock_real, use_container_width=True, hide_index=True)
            else:
                st.warning("Bodega vacía.")

        # PESTAÑA 3: HISTORIAL (SELECTOR)
        with t_mov:
            st.markdown("### 🚦 Historial")
            if 'tipo' in df.columns:
                filtro = st.radio("Ver:", ["Todos", "Enviados", "Recibidos"], horizontal=True)
                if filtro == "Enviados":
                    st.dataframe(df[df['tipo'].astype(str).str.lower().str.contains('enviado')], use_container_width=True)
                elif filtro == "Recibidos":
                    st.dataframe(df[df['tipo'].astype(str).str.lower().str.contains('recibido')], use_container_width=True)
                else:
                    st.dataframe(df, use_container_width=True)

        # PESTAÑA 4: GRÁFICAS
        with t_graf:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Top Marcas**")
                if 'marca' in df.columns: st.bar_chart(df['marca'].value_counts().head(5), color="#2e7d32")
            with c2:
                st.markdown("**Top Equipos**")
                if 'equipo' in df.columns: st.bar_chart(df['equipo'].value_counts().head(5), color="#1F4E78")

        st.divider()
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Base (CSV)", csv, "inventario.csv", "text/csv")
    else:
        st.warning("Sin datos.")
