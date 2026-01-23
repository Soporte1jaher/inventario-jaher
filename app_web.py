import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd
import re
import time

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA
# ==========================================
st.set_page_config(page_title="LAIA", page_icon="🧠", layout="wide")

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
        "message": "LAIA UPDATE",
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

    # --- FASE 1: LIMPIEZA NEURONAL ---
    # Normalizamos todo para que "Mouse", "mouse " y "MOUSE" sean lo mismo
    df_c.columns = df_c.columns.str.lower().str.strip()
    mapa = {'cant': 'cantidad', 'equipos': 'equipo', 'condicion': 'estado'}
    df_c = df_c.rename(columns=mapa)
    
    # Rellenamos nulos numéricos
    df_c['cantidad'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(1)

    # --- FASE 2: LÓGICA DE CLASIFICACIÓN (ACTIVO vs CONSUMIBLE) ---
    def procesar_fila(row):
        # Extraemos datos crudos
        equipo = str(row.get('equipo', '')).lower().strip()
        marca = str(row.get('marca', '')).strip()
        serie = str(row.get('serie', '')).lower().strip()
        estado = str(row.get('estado', '')).lower().strip()
        tipo = str(row.get('tipo', '')).lower().strip()
        dest = str(row.get('destino', '')).lower().strip()
        cant = row['cantidad']

        # 1. INTELIGENCIA DE ESTADO:
        # Si está dañado, NO cuenta como stock disponible para uso.
        if 'dañ' in estado or 'mal' in estado or 'rot' in estado or 'triz' in estado:
            return 0 # Lo sacamos del conteo de "Disponibles"

        # 2. INTELIGENCIA DE CATEGORÍA:
        # Lista de cosas que SIEMPRE son bulto (Periféricos)
        es_periferico_puro = any(x in equipo for x in [
            'mouse', 'teclado', 'cable', 'cargador', 'limpiador', 'ponchadora', 
            'adaptador', 'funda', 'mochila', 'candado', 'pasta', 'tornillo'
        ])
        
        # Validamos si es una serie real o basura ("n/a", "null")
        tiene_serie_real = len(serie) > 3 and not any(x in serie for x in ['n/a', 'none', 'null', 'sin', 'generi'])

        # REGLA DE ORO:
        # Si es un Activo (Laptop/CPU) con serie real -> NO suma al bulto (se controla por unidad).
        # Si es Periférico -> SUMA/RESTA al bulto.
        if tiene_serie_real and not es_periferico_puro:
            return 0 

        # 3. MATEMÁTICA DE FLUJO:
        # Stock = Lo que entra (+) menos lo que sale (-)
        if dest == 'stock': return cant
        if 'env' in tipo or 'sal' in tipo: return -cant
        
        # Si es una devolución a bodega también suma
        if 'rec' in tipo and 'stock' not in dest: return cant 
        
        return 0

    df_c['val'] = df_c.apply(procesar_fila, axis=1)

    # --- FASE 3: AGRUPACIÓN INTELIGENTE ---
    # Normalizamos nombres antes de agrupar
    df_c['marca'] = df_c['marca'].apply(lambda x: "Genérica" if str(x).lower() in ['n/a', 'null', '', 'none'] else str(x).title())
    df_c['equipo'] = df_c['equipo'].str.title()

    # Agrupamos (Sumamos todo lo bueno)
    stock = df_c.groupby(['equipo', 'marca'])['val'].sum().reset_index()
    stock.columns = ['Equipo', 'Marca', 'Stock_Disponible']

    # Filtro Final: Solo mostramos lo que existe (>0) y ordenamos
    return stock[stock['Stock_Disponible'] > 0].sort_values('Equipo')
    # ==========================================
# 5. INTERFAZ
# ==========================================
st.title("🤖 LAIA v21.0")
t1, t2, t3, t4 = st.tabs(["📝 Registro Inteligente", "💬 Chat Consultor", "🗑️ Limpieza Quirúrgica", "📊 BI & Historial"])
# --- TAB 1: REGISTRO CORREGIDO (LÓGICA BLINDADA ANTI-STOCK PARA DAÑADOS) ---
with t1:
    st.subheader("📝 Gestión de Movimientos")
    st.info("🧠 IA V70: Dañados aparecen en lista Recibidos (No Stock).")
    
    texto_input = st.text_area("Orden Logística:", height=200, 
        placeholder="Ej: Me llegó un Monitor AOC serie 888 roto... / Recibí 10 mouses...")

    if st.button("EJECUTAR ANÁLISIS", type="primary"):
        if texto_input.strip():
            with st.spinner("Procesando lógica de inventario..."):
                try:
                    client = genai.Client(api_key=API_KEY)

                    # PROMPT:
                    prompt = f"""
                    Analiza: "{texto_input}"
                    
                    INSTRUCCIONES:
                    1. **ESTADO**: Busca "roto", "trizado", "falla", "no vale" -> "Dañado". Si no -> "Bueno".
                    2. **TIPO**: "Recibido" (Entrada) o "Enviado" (Salida).
                    3. **CATEGORÍA**:
                       - Periféricos (Mouse, Cable, Teclado) -> SERIE "N/A".
                       - Equipos (Laptop, CPU, Monitor) -> EXTRAE LA SERIE REAL.
                    
                    FORMATO: [{{ "destino": "...", "tipo": "...", "cantidad": 1, "equipo": "...", "marca": "...", "serie": "...", "estado": "...", "reporte": "..." }}]
                    """

                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                    json_limpio = extraer_json(resp.text)

                    if json_limpio:
                        datos = json.loads(json_limpio)
                        fecha = obtener_fecha_ecuador()
                        
                        # Periféricos que van al bulto
                        LISTA_PERIFERICOS = ['mouse', 'teclado', 'cable', 'cargador', 'limpiador', 'ponchadora', 'funda', 'adaptador', 'botella']

                        for d in datos:
                            d["fecha"] = fecha
                            
                            # 1. ANALIZAR DAÑOS
                            full_text = (str(d.get("estado", "")) + " " + str(d.get("reporte", ""))).lower()
                            es_danado = any(x in full_text for x in ["dañ", "triz", "rot", "mal", "no enc", "falla", "golpe"])
                            
                            if es_danado:
                                d["estado"] = "Dañado"
                            else:
                                if not d.get("estado") or d["estado"] == "No especificada":
                                    d["estado"] = "Bueno"

                            # 2. DEFINIR TIPO
                            if "env" in str(d.get("tipo", "")).lower():
                                d["tipo"] = "Enviado"
                            else:
                                d["tipo"] = "Recibido"

                            # ==========================================================
                            # 3. LÓGICA DE DESTINO (LA SOLUCIÓN A TU IRA)
                            # ==========================================================
                            if d["tipo"] == "Recibido":
                                if es_danado:
                                    # SI ESTÁ DAÑADO: NO ponemos "Stock" para que salga en la lista principal.
                                    # Ponemos "Bodega" o "Ingreso". Tu Excel lo mostrará en Recibidos.
                                    d["destino"] = "Bodega" 
                                else:
                                    # SI ESTÁ BUENO: Ponemos "Stock" (Se va a saldos).
                                    d["destino"] = "Stock"

                            elif d["tipo"] == "Enviado":
                                if not d.get("destino"): d["destino"] = "Agencia"

                            # 4. SERIES (Periféricos N/A vs Equipos con Serie)
                            nom_equipo = str(d.get("equipo", "")).lower()
                            es_periferico = any(x in nom_equipo for x in LISTA_PERIFERICOS)
                            
                            if es_periferico:
                                d["serie"] = "N/A" # Periférico -> Bulto
                                if d.get("marca", "").lower() not in ["hp", "dell", "lenovo", "samsung", "lg", "aoc"]:
                                    d["marca"] = "Genérica"
                            else:
                                # Equipo -> RESPETA LA SERIE
                                s_temp = str(d.get("serie", "")).strip()
                                if s_temp.lower() in ["", "n/a", "no especificada", "null"]:
                                    d["serie"] = "No especificada"
                                else:
                                    d["serie"] = s_temp.upper()

                            # 5. Limpiezas finales
                            m_raw = str(d.get("marca", "")).lower().strip()
                            if m_raw in ["", "null", "none", "n/a", "no especificada"]: d["marca"] = "Genérica"
                            else: d["marca"] = d["marca"].title()

                            try: d["cantidad"] = int(d.get("cantidad", 1))
                            except: d["cantidad"] = 1

                        if enviar_buzon(datos):
                            st.success(f"✅ REGISTRO OK: {len(datos)} items.")
                            st.table(pd.DataFrame(datos))
                        else:
                            st.error("Error al guardar.")
                    else:
                        st.warning("La IA no entendió.")
                except Exception as e:
                    st.error(f"Error: {e}")
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

    datos, _ = obtener_github(f"{FILE_HISTORICO}?nocache={time.time()}")
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
