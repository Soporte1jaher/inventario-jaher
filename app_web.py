import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd

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

# CORREGIDO: Se agregó la variable {GITHUB_TOKEN} dentro de las llaves
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Cache-Control": "no-cache"}

# --- FUNCIONES DE APOYO (ESTRUCTURA ORIGINAL EXPANDIDA) ---
def obtener_fecha_ecuador():
    return (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")

def obtener_github(archivo):
    # CORREGIDO: Se agregaron las variables a la URL
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
    # CORREGIDO: Se agregaron las variables a la URL
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

# --- INTERFAZ ---
st.title("🤖 LAIA NEURAL ENGINE v9.0")
t1, t2, t3, t4 = st.tabs(["📝 Registro Inteligente", "💬 Chat Consultor", "🗑️ Limpieza Quirúrgica", "📊 BI & Historial"])

# --- TAB 1: REGISTRO & ESTRATEGIA (IA MEJORADA V9.3) ---
# --- TAB 1: REGISTRO & ESTRATEGIA (LÓGICA BLINDADA V9.5) ---
with t1:
    st.subheader("📝 Gestión de Movimientos")
    st.info("💡 IA V9.5: Lógica Unificada. Corrige ortografía, detecta daños, crea reportes IT y fuerza el tipo a 'Enviado' o 'Recibido'.")
    texto_input = st.text_area("Orden Logística:", height=200, placeholder="Ej: Envié un CPU a Manta. O me llegó una Laptop de Pedernales con pantalla rota para informe...")
    
    if st.button("🚀 EJECUTAR ACCIÓN INTELIGENTE", type="primary"):
        if texto_input.strip():
            with st.spinner("LAIA procesando: Estandarizando Tipo, Estado y Reportes..."):
                try:
                    client = genai.Client(api_key=API_KEY)
                    
                    # --- PROMPT MAESTRO (FUSIÓN DE TODAS LAS REGLAS) ---
                    prompt = f"""
                    Actúa como un Auditor de Inventario y Experto Logístico.
                    TEXTO DE ENTRADA: "{texto_input}"
                    
                    SIGUE ESTAS 5 REGLAS DE ORO PARA GENERAR EL JSON:

                    1. **TIPO DE MOVIMIENTO (ESTRICTO - BINARIO)**:
                       - Este campo SOLO admite: "Recibido" o "Enviado".
                       - Si el texto implica entrada (Llegó, Recibí, Inventariar, A stock, Vino de) -> TIPO: "Recibido".
                       - Si el texto implica salida (Envié, Se fue, Para [Ciudad], Salida) -> TIPO: "Enviado".
                       - 🚫 PROHIBIDO poner nombres de equipos (CPU, Laptop) en este campo.

                    2. **DIAGNÓSTICO DE ESTADO**:
                       - "Dañado": Fallas funcionales (No prende, Pantalla rota, Disco dañado).
                       - "Usado": Defectos estéticos (Rayones, Sucio).
                       - "Nuevo": Solo si se especifica explícitamente.

                    3. **INFORME TÉCNICO (IT)**:
                       - Si pide "Revisar", "Diagnosticar", "Informe" o "IT": AGREGA "[REQUIERE IT]" al inicio del campo 'reporte'.

                    4. **CORRECCIÓN Y LIMPIEZA**:
                       - Corrige ortografía (ej: "cragador"->"Cargador", "mause"->"Mouse").
                       - Estandariza Marcas (hp -> HP).

                    5. **LÓGICA DE STOCK Y ACCESORIOS**:
                       - "A Stock" o Consumibles masivos -> Destino: "Stock".
                       - Accesorios adjuntos ("Laptop con cargador") -> Van al 'reporte', NO fila nueva.
                       - Accesorios sueltos ("50 mouses") -> Fila propia.

                    FORMATO SALIDA (JSON):
                    [{{ "destino": "...", "tipo": "Recibido/Enviado", "cantidad": 1, "equipo": "...", "marca": "...", "serie": "...", "estado": "...", "ubicacion": "...", "reporte": "..." }}]
                    """
                    
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                    json_limpio = extraer_json(resp.text)
                    
                    if json_limpio:
                        datos = json.loads(json_limpio)
                        fecha = obtener_fecha_ecuador()
                        
                        # --- CAPA DE SEGURIDAD PYTHON (Anti-Alucinaciones) ---
                        for d in datos: 
                            d["fecha"] = fecha
                            
                            # 1. Corrección forzada de TIPO (Arregla el error de "CPU" en tipo)
                            tipo_raw = str(d.get("tipo", "")).lower()
                            if "env" in tipo_raw or "sal" in tipo_raw:
                                d["tipo"] = "Enviado"
                            elif "rec" in tipo_raw or "lleg" in tipo_raw or "ing" in tipo_raw:
                                d["tipo"] = "Recibido"
                            else:
                                # Si la IA puso cualquier cosa rara, asumimos Recibido por defecto
                                d["tipo"] = "Recibido"

                            # 2. Corrección forzada de ESTADO
                            estado_raw = str(d.get("estado", "")).lower()
                            if "dañ" in estado_raw or "rot" in estado_raw or "mal" in estado_raw:
                                d["estado"] = "Dañado"

                        if enviar_buzon(datos):
                            st.success(f"✅ LAIA procesó correctamente {len(datos)} registros.")
                            
                            # Alertas visuales
                            if any(d.get('estado') == 'Dañado' for d in datos):
                                st.warning("⚠️ Se detectaron equipos DAÑADOS. Se enviarán a la hoja de reportes.")
                            
                            st.table(pd.DataFrame(datos))
                        else:
                            st.error("Error de conexión con GitHub.")
                    else:
                        st.warning("La IA no pudo interpretar la orden. Intenta ser más claro.")
                            
                except Exception as e:
                    st.error(f"Error crítico en IA: {e}")

# --- TAB 2: CHAT IA (CON CONTEXTO DE INVENTARIO) ---
with t2:
    st.subheader("💬 Consulta Inteligente")
    if "messages" not in st.session_state: st.session_state.messages = []
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p_chat := st.chat_input("¿Qué equipos tenemos en Ambato?"):
        st.session_state.messages.append({"role": "user", "content": p_chat})
        with st.chat_message("user"): st.markdown(p_chat)
        
        # Inyectamos el historial completo para que la IA responda con la verdad
        hist, _ = obtener_github(FILE_HISTORICO)
        # Convertir a string seguro para el prompt
        hist_str = json.dumps(hist[-150:]) if hist else "[]"
        contexto = f"INVENTARIO ACTUAL: {hist_str}. Responde basado solo en estos datos."
        
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=contexto + p_chat)
        
        with st.chat_message("assistant"): st.markdown(resp.text)
        st.session_state.messages.append({"role": "assistant", "content": resp.text})

# --- TAB 3: LIMPIEZA QUIRÚRGICA (LA MAGIA QUE PEDISTE) ---
with t3:
    st.subheader("🗑️ Eliminación por Razonamiento")
    st.warning("⚠️ Aquí puedes ser descriptivo: 'Borra el CPU de Ambato' o 'Borra los mouses dañados'")
    txt_borrar = st.text_input("¿Qué quieres eliminar?")
    
    if st.button("🔥 EJECUTAR BORRADO DE PRECISIÓN"):
        if txt_borrar:
            with st.spinner("LAIA localizando el registro en el historial..."):
                # PASO 1: Obtener historial para que la IA identifique el registro
                hist, _ = obtener_github(FILE_HISTORICO)
                contexto_borrado = json.dumps(hist[-100:]) if hist else "[]"
                
                client = genai.Client(api_key=API_KEY)
                # CORREGIDO: Se insertó {txt_borrar} en el prompt
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

# --- TAB 4: BI & HISTORIAL (DASHBOARD INTELIGENTE V2.0) ---
# --- TAB 4: BI & HISTORIAL (DASHBOARD V3.0 - MÉTRICAS DE FLUJO) ---
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
        # Aseguramos columnas y limpieza básica
        for col in ['destino', 'estado', 'marca', 'equipo', 'tipo', 'serie']:
            if col not in df.columns: df[col] = "N/A"
        
        # Convertimos a string para evitar errores
        df['tipo'] = df['tipo'].astype(str)
        df['destino'] = df['destino'].astype(str)
        
        # Filtros Clave
        df_stock = df[df['destino'].str.lower() == 'stock'].copy()
        df_bad = df[df['estado'].astype(str).str.lower().str.contains('dañ')].copy()
        
        # Conteo para KPIs
        # Usamos str.contains para atrapar "Enviado", "Envío", etc.
        cant_env = len(df[df['tipo'].str.lower().str.contains('enviado') | df['tipo'].str.lower().str.contains('salida')])
        cant_rec = len(df[df['tipo'].str.lower().str.contains('recibido') | df['tipo'].str.lower().str.contains('entrada')])
        
        # --- NUEVAS MÉTRICAS KPI (SOLICITADAS) ---
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("📤 Total Enviados", cant_env, delta="Salidas Históricas", delta_color="off")
        kpi2.metric("📥 Total Recibidos", cant_rec, delta="Entradas Históricas", delta_color="normal")
        kpi3.metric("📦 En Stock Actual", len(df_stock), delta="Disponibles")
        kpi4.metric("⚠️ Equipos Dañados", len(df_bad), delta="Atención", delta_color="inverse")
        
        st.divider()

        # --- SUB-PESTAÑAS ---
        st_t1, st_t2, st_t3, st_t4, st_t5 = st.tabs(["📂 Maestro", "📦 Bodega", "🚚 Tráfico", "⚠️ HOSPITAL", "🕵️ Auditoría"])
        
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

        # 2. VISTA STOCK
        with st_t2:
            st.info("Vista filtrada: Artículos actualmente en Bodega.")
            if not df_stock.empty:
                st.dataframe(df_stock, use_container_width=True, hide_index=True)
                st.caption("Conteo rápido:")
                st.json(df_stock['equipo'].value_counts().to_dict())
            else:
                st.warning("Bodega vacía.")

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

        # 5. AUDITORÍA (RESPUESTA A TU PREGUNTA DE SERIES DUPLICADAS)
        with st_t5:
            st.warning("🕵️ Detector de Inconsistencias Lógicas")
            st.markdown("Aquí aparecerán series que tienen **'Enviado' seguido de 'Enviado'** (posible error de doble salida sin retorno).")
            
            # Lógica para detectar series enviadas 2 veces seguidas sin recibir
            series_problem = []
            if 'serie' in df.columns and 'tipo' in df.columns:
                # Filtramos solo activos con serie real
                df_ser = df[df['serie'].str.len() > 3].copy() 
                # Agrupamos por serie
                for ser, group in df_ser.groupby('serie'):
                    if len(group) > 1:
                        # Asumimos orden cronológico del excel
                        tipos = group['tipo'].str.lower().tolist()
                        for i in range(len(tipos) - 1):
                            # Si hay dos "enviado" seguidos...
                            if 'env' in tipos[i] and 'env' in tipos[i+1]:
                                series_problem.append({"Serie": ser, "Equipo": group.iloc[0].get('equipo'), "Error": "Doble Salida Detectada"})
                                break
            
            if series_problem:
                st.table(pd.DataFrame(series_problem))
            else:
                st.success("✅ La lógica del inventario parece consistente (No hay doble envío de series).")

        # --- DESCARGA ---
        st.divider()
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar CSV", csv, "inventario.csv", "text/csv")

    else:
        st.warning("⚠️ Sin conexión a base de datos.")
