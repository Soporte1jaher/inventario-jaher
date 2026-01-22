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

# HEADER CORREGIDO
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Cache-Control": "no-cache"}

# --- FUNCIONES DE APOYO (ESTRUCTURA ORIGINAL EXPANDIDA) ---
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

# --- NUEVA FUNCIÓN: CÁLCULO MATEMÁTICO V14 (ESTA ES LA MAGIA QUE ARREGLA LOS CABLES) ---
def calcular_stock_web(df):
    if df.empty: return pd.DataFrame()
    df_c = df.copy()
    
    # --- PARCHE 1: ARREGLAR NOMBRES DE COLUMNAS (Cant -> cantidad) ---
    # Convertimos encabezados a minúsculas y quitamos espacios
    df_c.columns = df_c.columns.str.strip().str.lower()
    
    # Mapeamos los nombres de tu foto a lo que usa el cálculo
    mapa = {
        'cant': 'cantidad', 
        'condición': 'estado', 
        'condicion': 'estado',
        'cond': 'estado'
    }
    df_c = df_c.rename(columns=mapa)
    
    # --- PARCHE 2: ARREGLAR "None" vs "Genérica" ---
    # Aseguramos que existan las columnas y sean texto minúscula
    for col in ['marca', 'estado', 'serie', 'tipo', 'destino', 'equipo']:
        if col not in df_c.columns: df_c[col] = "n/a"
        df_c[col] = df_c[col].astype(str).str.strip().str.lower()

    # Convertimos cualquier variante de "vacío" a una palabra estándar
    # Así "Cable HDMI None" (Salida) restará a "Cable HDMI Genérica" (Entrada)
    nulos = ['n/a', 'none', 'nan', 'null', '', 'sin marca', 'genérica', 'generica']
    
    df_c['marca'] = df_c['marca'].replace(nulos, 'genérica')
    df_c['estado'] = df_c['estado'].replace(nulos, 'nuevo')
    
    # Asegurar números (Si falla, pone 1)
    if 'cantidad' not in df_c.columns: df_c['cantidad'] = 1
    df_c['cantidad'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(1)
    
    # --- PARCHE 3: MATEMÁTICA (+/-) ---
    def flujo(row):
        tipo = row['tipo']
        dest = row['destino']
        ser = row['serie']
        cant = row['cantidad']
        
        # Si tiene serie larga (>3 letras) y no es nula, es Activo Único -> NO se suma al bulto
        es_activo = len(ser) > 3 and not any(x in ser for x in nulos) and ser != "sin serie"
        if es_activo: return 0
        
        # Entradas a stock suman
        if dest == 'stock': return cant
        
        # Salidas restan
        if 'env' in tipo or 'sal' in tipo: return -cant
        
        return 0

    df_c['val'] = df_c.apply(flujo, axis=1)
    
    # --- AGRUPAR RESULTADOS ---
    df_c['equipo'] = df_c['equipo'].str.capitalize()
    stock = df_c.groupby(['equipo', 'marca'])['val'].sum().reset_index()
    
    # Devolver tabla bonita con columnas correctas
    stock.columns = ['Equipo', 'Marca', 'Cantidad']
    
    return stock[stock['Cantidad'] > 0]

# --- INTERFAZ ---
st.title("🤖 LAIA NEURAL ENGINE v14.0")
t1, t2, t3, t4 = st.tabs(["📝 Registro Inteligente", "💬 Chat Consultor", "🗑️ Limpieza Quirúrgica", "📊 BI & Historial"])

# --- TAB 1: REGISTRO & ESTRATEGIA ---
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
                            
                            # --- SEGURIDAD PYTHON (LÓGICA BLINDADA V16.5) ---
                            tipo_ia = str(d.get("tipo", "")).lower()
                            dest_ia = str(d.get("destino", "")).lower()
                            
                            # REGLA 1: Si es salida explícita, se respeta como ENVIADO (Resta)
                            if any(x in tipo_ia for x in ["env", "sal", "desp"]):
                                d["tipo"] = "Enviado"
                                # Si la IA se equivocó y puso destino stock en una salida, lo corregimos a "Salida General"
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

# --- TAB 2: CHAT IA (CON BOTÓN DE LIMPIAR) ---
with t2:
    col_c1, col_c2 = st.columns([4, 1])
    with col_c1:
        st.subheader("💬 Consulta Inteligente")
    with col_c2:
        if st.button("🧹 Nueva Charla"):
            st.session_state.messages = []
            st.rerun()

    if "messages" not in st.session_state: st.session_state.messages = []
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p_chat := st.chat_input("¿Qué equipos tenemos en Ambato?"):
        st.session_state.messages.append({"role": "user", "content": p_chat})
        with st.chat_message("user"): st.markdown(p_chat)
        
        # OBTENER DATOS Y CALCULAMOS STOCK REAL PARA LA IA
        hist, _ = obtener_github(FILE_HISTORICO)
        df_hist = pd.DataFrame(hist)
        df_real = calcular_stock_web(df_hist) # Usamos la función V14
        
        # Contexto enriquecido
        contexto = f"""
        INVENTARIO REAL (Saldos Calculados Matemáticamente):
        {df_real.to_string(index=False) if not df_real.empty else "Sin stock"}
        
        HISTORIAL COMPLETO: {json.dumps(hist[-150:])}
        
        USUARIO: {p_chat}
        Responde basándote en la tabla de INVENTARIO REAL si preguntan cantidades.
        """
        
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=contexto)
        
        with st.chat_message("assistant"): st.markdown(resp.text)
        st.session_state.messages.append({"role": "assistant", "content": resp.text})

# --- TAB 3: LIMPIEZA QUIRÚRGICA ---
with t3:
    st.subheader("🗑️ Eliminación por Razonamiento")
    st.warning("⚠️ Aquí puedes ser descriptivo: 'Borra el CPU de Ambato' o 'Borra los mouses dañados'")
    txt_borrar = st.text_input("¿Qué quieres eliminar?")
    
    if st.button("🔥 EJECUTAR BORRADO DE PRECISIÓN"):
        if txt_borrar:
            with st.spinner("LAIA localizando el registro en el historial..."):
                hist, _ = obtener_github(FILE_HISTORICO)
                contexto_borrado = json.dumps(hist[-100:]) if hist else "[]"
                
                client = genai.Client(api_key=API_KEY)
                prompt_b = f"""
                DADOS ESTOS REGISTROS: {contexto_borrado}
                ORDEN DEL USUARIO: "{txt_borrar}"
                TAREA: Identifica qué registro exacto quiere borrar. 
                Responde UNICAMENTE un JSON con este formato:
                [{{"accion": "borrar_quirurgico", "serie": "SERIE_A_BORRAR", "equipo": "NOMBRE", "motivo": "RAZON"}}]
                Si el usuario dice "borra todo", la accion es "borrar_todo".
                """
                resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_b)
                orden_json = extraer_json(resp.text)
                
                if orden_json:
                    try:
                        data_borrado = json.loads(orden_json)
                        if enviar_buzon(data_borrado):
                            st.success("🎯 LAIA identificó el registro y envió la orden de eliminación.")
                            st.json(orden_json)
                    except Exception as e:
                        st.error(f"Error procesando respuesta de borrado: {e}")
                else:
                    st.error("LAIA no pudo identificar qué registro borrar.")

# --- TAB 4: BI & HISTORIAL (MEJORADO CON STOCK REAL Y KPIs) ---
with t4:
    c_head1, c_head2 = st.columns([3, 1])
    c_head1.subheader("📊 Dashboard de Control de Activos")
    if c_head2.button("🔄 Actualizar Datos en Tiempo Real"):
        st.rerun()

    datos, _ = obtener_github(FILE_HISTORICO)
    
    if datos:
        df = pd.DataFrame(datos)
        
        # --- PRE-PROCESAMIENTO ---
        for col in ['destino', 'estado', 'marca', 'equipo', 'tipo', 'serie']:
            if col not in df.columns: df[col] = "N/A"
        
        df['tipo'] = df['tipo'].astype(str)
        df['destino'] = df['destino'].astype(str)
        
        # --- CÁLCULO DE STOCK REAL ---
        df_stock_real = calcular_stock_web(df)
        df_bad = df[df['estado'].astype(str).str.lower().str.contains('dañ')].copy()
        
        # KPIs
        cant_env = len(df[df['tipo'].str.lower().str.contains('enviado') | df['tipo'].str.lower().str.contains('salida')])
        cant_rec = len(df[df['tipo'].str.lower().str.contains('recibido') | df['tipo'].str.lower().str.contains('entrada')])
        total_unidades = int(df_stock_real['Cantidad'].sum()) if not df_stock_real.empty else 0
        
        # Métricas visuales
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("⚠️ Dañados", len(df_bad), delta="Prioridad Alta", delta_color="inverse")
        kpi2.metric("📦 Stock Disp.", total_unidades, delta="Unidades")
        kpi3.metric("📤 Enviados", cant_env, delta_color="off")
        kpi4.metric("📥 Recibidos", cant_rec)
        
        st.divider()

        # --- PESTAÑAS EN EL ORDEN SOLICITADO ---
        t_bad, t_stock, t_mov, t_graf = st.tabs(["⚠️ Equipos Dañados", "📦 Stock (Saldos)", "🚚 Enviados/Recibidos", "📊 Gráficas"])
        
        # 1. EQUIPOS DAÑADOS
        with t_bad:
            st.error("🚨 Lista de equipos que requieren reparación o baja:")
            if not df_bad.empty:
                # Ponemos el reporte primero para leer rápido el daño
                cols = list(df_bad.columns)
                if 'reporte' in cols: cols.insert(0, cols.pop(cols.index('reporte')))
                st.dataframe(df_bad[cols], use_container_width=True)
            else:
                st.success("¡Todo limpio! No hay equipos dañados.")

        # 2. STOCK (SALDOS)
        with t_stock:
            st.info("Inventario Real Disponible (Calculado: Entradas - Salidas).")
            if not df_stock_real.empty:
                # Formato idéntico al Excel
                df_mostrar = df_stock_real.rename(columns={
                    'Cantidad': 'Stock_Disponible',
                    'Equipo': 'Equipo',
                    'Marca': 'Marca'
                })
                st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
            else:
                st.warning("Bodega vacía.")

        # 3. ENVIADOS Y RECIBIDOS (SELECTOR)
        with t_mov:
            st.markdown("### 🚦 Historial de Movimientos")
            filtro = st.radio("Selecciona tipo de movimiento:", ["Todos", "Enviados", "Recibidos"], horizontal=True)
            
            if filtro == "Enviados":
                st.dataframe(df[df['tipo'].str.lower().str.contains('env')], use_container_width=True)
            elif filtro == "Recibidos":
                st.dataframe(df[df['tipo'].str.lower().str.contains('rec')], use_container_width=True)
            else:
                st.dataframe(df, use_container_width=True)

        # 4. GRÁFICAS
        with t_graf:
            st.markdown("### 📈 Estadísticas Visuales")
            col_g1, col_g2 = st.columns(2)
            
            with col_g1:
                st.markdown("**Top Marcas en Movimiento**")
                if 'marca' in df.columns:
                    st.bar_chart(df['marca'].value_counts().head(10), color="#2e7d32")
            
            with col_g2:
                st.markdown("**Distribución por Tipo de Equipo**")
                if 'equipo' in df.columns:
                    st.bar_chart(df['equipo'].value_counts().head(10), color="#1F4E78")

        # Botón de Descarga Global
        st.divider()
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Base Completa (CSV)", csv, "inventario_jaher.csv", "text/csv")

    else:
        st.warning("⚠️ Sin conexión a base de datos.")
