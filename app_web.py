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
        # CORREGIDO: El split debe buscar las comillas triples del markdown
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

# --- NUEVA FUNCIÓN: CÁLCULO MATEMÁTICO PARA WEB (La clave para el stock real) ---
def calcular_stock_web(df):
    if df.empty: return pd.DataFrame()
    df_c = df.copy()
    
    # 1. Normalización
    for col in ['marca', 'estado', 'serie', 'tipo', 'destino', 'equipo']:
        if col not in df_c.columns: df_c[col] = "N/A"
        df_c[col] = df_c[col].astype(str).str.strip()
    
    # Unificación para que resten bien
    df_c['marca'] = df_c['marca'].replace(['N/A', 'n/a', 'None', '', 'nan'], 'Genérica')
    df_c['estado'] = df_c['estado'].replace(['N/A', 'n/a', 'None', '', 'nan'], 'Nuevo')
    df_c['cantidad'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(1)
    
    # 2. Lógica Matemática (+/-)
    def flujo(row):
        tipo = row['tipo'].lower()
        dest = row['destino'].lower()
        ser = row['serie'].lower()
        cant = row['cantidad']
        
        # Si es activo único con serie larga, no se suma al bulto
        es_activo = len(ser) > 3 and "n/a" not in ser and "sin serie" not in ser
        if es_activo: return 0
        
        if dest == 'stock': return cant # Entra
        if 'enviado' in tipo or 'salida' in tipo: return -cant # Sale
        return 0

    df_c['val'] = df_c.apply(flujo, axis=1)
    
    # 3. Agrupar
    stock = df_c.groupby(['equipo', 'marca'])['val'].sum().reset_index()
    return stock[stock['val'] > 0] # Solo stock positivo

# --- INTERFAZ ---
st.title("🤖 LAIA NEURAL ENGINE v12.5")
t1, t2, t3, t4 = st.tabs(["📝 Registro Inteligente", "💬 Chat Consultor", "🗑️ Limpieza Quirúrgica", "📊 BI & Historial"])

# --- TAB 1: REGISTRO & ESTRATEGIA ---
with t1:
    st.subheader("📝 Gestión de Movimientos")
    st.info("💡 IA V9.5: Lógica Unificada. Corrige ortografía, detecta daños, crea reportes IT y fuerza el tipo a 'Enviado' o 'Recibido'.")
    texto_input = st.text_area("Orden Logística:", height=200, placeholder="Ej: Envié un CPU a Manta. O me llegó una Laptop de Pedernales con pantalla rota para informe...")
    
    if st.button("🚀 EJECUTAR ACCIÓN INTELIGENTE", type="primary"):
        if texto_input.strip():
            with st.spinner("LAIA procesando: Estandarizando Tipo, Estado y Reportes..."):
                try:
                    client = genai.Client(api_key=API_KEY)
                    
                    prompt = f"""
                    Actúa como un Auditor de Inventario y Experto Logístico.
                    TEXTO DE ENTRADA: "{texto_input}"
                    
                    SIGUE ESTAS 5 REGLAS DE ORO PARA GENERAR EL JSON:

                    1. **TIPO DE MOVIMIENTO (ESTRICTO - BINARIO)**:
                       - Este campo SOLO admite: "Recibido" o "Enviado".
                       - Si implica entrada (Llegó, Recibí, Inventariar, A stock) -> TIPO: "Recibido".
                       - Si implica salida (Envié, Se fue, Para [Ciudad], Salida) -> TIPO: "Enviado".
                       - 🚫 PROHIBIDO poner nombres de equipos en este campo.

                    2. **DIAGNÓSTICO DE ESTADO**:
                       - "Dañado": Fallas funcionales.
                       - "Usado": Defectos estéticos.
                       - "Nuevo": Solo si se especifica.

                    3. **INFORME TÉCNICO (IT)**:
                       - Si pide revisar/diagnosticar: AGREGA "[REQUIERE IT]" al inicio del campo 'reporte'.

                    4. **CORRECCIÓN Y LIMPIEZA**:
                       - Corrige ortografía ("cragador"->"Cargador").
                       - Estandariza Marcas.

                    5. **LÓGICA DE STOCK Y ACCESORIOS**:
                       - "A Stock" -> Destino: "Stock".
                       - "Laptop con cargador" -> Cargador en reporte.
                       - "50 mouses" -> Cantidad: 50.

                    FORMATO SALIDA (JSON):
                    [{{ "destino": "...", "tipo": "Recibido/Enviado", "cantidad": 1, "equipo": "...", "marca": "...", "serie": "...", "estado": "...", "ubicacion": "...", "reporte": "..." }}]
                    """
                    
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                    json_limpio = extraer_json(resp.text)
                    
                    if json_limpio:
                        datos = json.loads(json_limpio)
                        fecha = obtener_fecha_ecuador()
                        
                        # --- CAPA DE SEGURIDAD PYTHON ---
                        for d in datos: 
                            d["fecha"] = fecha
                            
                            # 1. Corrección forzada de TIPO
                            tipo_raw = str(d.get("tipo", "")).lower()
                            if "env" in tipo_raw or "sal" in tipo_raw:
                                d["tipo"] = "Enviado"
                            elif "rec" in tipo_raw or "lleg" in tipo_raw or "ing" in tipo_raw:
                                d["tipo"] = "Recibido"
                            else:
                                d["tipo"] = "Recibido" # Default

                            # 2. Corrección forzada de ESTADO
                            estado_raw = str(d.get("estado", "")).lower()
                            if "dañ" in estado_raw or "rot" in estado_raw or "mal" in estado_raw:
                                d["estado"] = "Dañado"

                        if enviar_buzon(datos):
                            st.success(f"✅ LAIA procesó correctamente {len(datos)} registros.")
                            if any(d.get('estado') == 'Dañado' for d in datos):
                                st.warning("⚠️ Se detectaron equipos DAÑADOS. Se enviarán a la hoja de reportes.")
                            st.table(pd.DataFrame(datos))
                        else:
                            st.error("Error de conexión con GitHub.")
                    else:
                        st.warning("La IA no pudo interpretar la orden. Intenta ser más claro.")
                            
                except Exception as e:
                    st.error(f"Error crítico en IA: {e}")

# --- TAB 2: CHAT IA (CON BOTÓN DE RECARGA AÑADIDO) ---
with t2:
    # AQUI ESTA EL CAMBIO QUE PEDISTE: Columnas para el botón de limpiar
    col_chat_head, col_chat_btn = st.columns([4, 1])
    with col_chat_head:
        st.subheader("💬 Consulta Inteligente")
    with col_chat_btn:
        if st.button("🧹 Limpiar Chat"):
            st.session_state.messages = []
            st.rerun()

    if "messages" not in st.session_state: st.session_state.messages = []
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p_chat := st.chat_input("¿Qué equipos tenemos en Ambato?"):
        st.session_state.messages.append({"role": "user", "content": p_chat})
        with st.chat_message("user"): st.markdown(p_chat)
        
        # OBTENER DATOS Y CALCULAR STOCK PARA QUE LA IA NO SE EQUIVOQUE
        hist, _ = obtener_github(FILE_HISTORICO)
        df_hist = pd.DataFrame(hist)
        df_real = calcular_stock_web(df_hist) # Usamos la función matemática nueva
        
        # Contexto enriquecido con cálculos reales
        contexto = f"""
        INVENTARIO REAL CALCULADO (Entradas - Salidas):
        {df_real.to_string(index=False) if not df_real.empty else "Sin stock"}
        
        HISTORIAL COMPLETO: {json.dumps(hist[-150:])}. 
        Responde basado en la tabla de INVENTARIO REAL si preguntan cantidades.
        """
        
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=contexto + p_chat)
        
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
    # 1. Cabecera y Botón de Recarga
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
        
        # CÁLCULO DE STOCK REAL (Para mostrar 19 en vez de 20)
        df_stock_real = calcular_stock_web(df)
        df_bad = df[df['estado'].astype(str).str.lower().str.contains('dañ')].copy()
        
        # Conteo para KPIs
        cant_env = len(df[df['tipo'].str.lower().str.contains('enviado') | df['tipo'].str.lower().str.contains('salida')])
        cant_rec = len(df[df['tipo'].str.lower().str.contains('recibido') | df['tipo'].str.lower().str.contains('entrada')])
        
        # --- METRICAS KPI ACTUALIZADAS ---
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("📤 Total Enviados", cant_env, delta="Salidas Históricas", delta_color="off")
        kpi2.metric("📥 Total Recibidos", cant_rec, delta="Entradas Históricas", delta_color="normal")
        # Aquí usamos el stock calculado
        kpi3.metric("📦 En Stock Real", int(df_stock_real['val'].sum()) if not df_stock_real.empty else 0, delta="Disponibles")
        kpi4.metric("⚠️ Equipos Dañados", len(df_bad), delta="Atención", delta_color="inverse")
        
        st.divider()

        # --- SUB-PESTAÑAS ---
        st_t1, st_t2, st_t3, st_t4, st_t5 = st.tabs(["📂 Maestro", "📦 Bodega Real", "🚚 Tráfico", "⚠️ HOSPITAL", "🕵️ Auditoría"])
        
        # 1. MAESTRO GENERAL
        with st_t1:
            st.markdown("### 📈 Resumen Global")
            col_g1, col_g2 = st.columns(2)
            if 'marca' in df.columns:
                col_g1.bar_chart(df['marca'].value_counts().head(5), color="#2e7d32")
                col_g1.caption("Marcas más frecuentes")
            if 'equipo' in df.columns:
                col_g2.bar_chart(df['equipo'].value_counts().head(5), color="#1F4E78")
                col_g2.caption("Tipos de equipo")
            st.dataframe(df, use_container_width=True, hide_index=True)

        # 2. VISTA STOCK REAL (USANDO EL CÁLCULO MATEMÁTICO)
        with st_t2:
            st.info("Vista filtrada: Stock real disponible (Entradas - Salidas).")
            if not df_stock_real.empty:
                st.dataframe(df_stock_real, use_container_width=True, hide_index=True)
            else:
                st.warning("Bodega vacía o sin stock calculado.")

        # 3. VISTA TRÁFICO
        with st_t3:
            st.markdown("### 🚦 Filtro de Movimientos")
            filtro = st.radio("Ver:", ["Enviados", "Recibidos"], horizontal=True)
            if filtro == "Enviados":
                st.dataframe(df[df['tipo'].str.lower().str.contains('env')], use_container_width=True)
            else:
                st.dataframe(df[df['tipo'].str.lower().str.contains('rec')], use_container_width=True)

        # 4. VISTA DAÑADOS
        with st_t4:
            st.error("🚨 Equipos reportados con daños")
            if not df_bad.empty:
                cols = list(df_bad.columns)
                if 'reporte' in cols: cols.insert(0, cols.pop(cols.index('reporte')))
                st.dataframe(df_bad[cols], use_container_width=True)
            else:
                st.success("Sin novedades de daños.")

        # 5. AUDITORÍA
        with st_t5:
            st.warning("🕵️ Detector de Inconsistencias Lógicas")
            st.markdown("Aquí aparecerán series que tienen 'Enviado' seguido de 'Enviado'.")
            
            series_problem = []
            if 'serie' in df.columns and 'tipo' in df.columns:
                df_ser = df[df['serie'].str.len() > 3].copy() 
                for ser, group in df_ser.groupby('serie'):
                    if len(group) > 1:
                        tipos = group['tipo'].str.lower().tolist()
                        for i in range(len(tipos) - 1):
                            if 'env' in tipos[i] and 'env' in tipos[i+1]:
                                series_problem.append({"Serie": ser, "Equipo": group.iloc[0].get('equipo'), "Error": "Doble Salida Detectada"})
                                break
            
            if series_problem:
                st.table(pd.DataFrame(series_problem))
            else:
                st.success("✅ La lógica del inventario parece consistente.")

        # --- DESCARGA ---
        st.divider()
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar CSV", csv, "inventario.csv", "text/csv")

    else:
        st.warning("⚠️ Sin conexión a base de datos.")
