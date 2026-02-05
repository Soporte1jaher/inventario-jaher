import streamlit as st
from openai import OpenAI
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd
import time

# ==========================================
# 1. CONFIGURACIÓN Y ESTILOS
# ==========================================
st.set_page_config(page_title="LAIA v91.2 - Auditora Senior", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2e7d32; color: white; border: none; }
    .stChatFloatingInputContainer { background-color: #0e1117; }
    .stDataFrame { background-color: #1e212b; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CREDENCIALES
# ==========================================
try:
    API_KEY = st.secrets["GPT_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Configura los Secrets (GITHUB_TOKEN y GPT_API_KEY).")
    st.stop()

client = OpenAI(api_key=API_KEY)

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"
FILE_LECCIONES = "lecciones.json"
HEADERS = {"Authorization": "token " + GITHUB_TOKEN, "Cache-Control": "no-cache"}

# ==========================================
# 3. FUNCIONES AUXILIARES
# ==========================================
def extraer_json(texto):
    try:
        texto = texto.replace("```json", "").replace("```", "").strip()
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio != -1 and fin > inicio:
            return texto[inicio:fin].strip()
        return ""
    except:
        return ""

def obtener_github(archivo):
    timestamp = int(time.time())
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}?t={timestamp}"    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        
        if resp.status_code == 200:
            d = resp.json()
            contenido_decodificado = base64.b64decode(d['content']).decode('utf-8')
            
            try:
                # Intentamos leer el JSON
                return json.loads(contenido_decodificado), d['sha']
            except json.JSONDecodeError:
                # 🛑 AQUÍ ESTÁ EL CAMBIO: Si falla, devolvemos None, None.
                # Esto activa la alarma en la función de enviar.
                st.error(f"⛔ ¡PELIGRO CRÍTICO! El archivo {archivo} está CORRUPTO en GitHub. Se ha bloqueado el sistema para evitar borrar datos.")
                return None, None
                
        elif resp.status_code == 404:
            # Si no existe, devolvemos lista vacía (esto sí es seguro)
            return [], None
        else:
            st.error(f"❌ Error GitHub {resp.status_code}: {resp.text}")
            return None, None
            
    except Exception as e:
        st.error(f"❌ Error de conexión: {str(e)}")
        return None, None

def enviar_github(archivo, datos, mensaje="LAIA Update"):
    # 1. Obtenemos lo que hay con cache-busting fuerte
    actuales, sha = obtener_github(archivo)
    
    # --- CANDADO ANTIBORRADO ---
    if actuales is None:
        st.error("❌ ERROR CRÍTICO: No se pudo leer la base de datos. Intento de guardado abortado para proteger los datos existentes.")
        return False

    # 2. Aseguramos que actuales sea una lista
    if not isinstance(actuales, list):
        actuales = []

    # 3. Añadimos lo nuevo al final (NO SOBRESCRIBIMOS)
    if isinstance(datos, list):
        actuales.extend(datos)
    else:
        actuales.append(datos)

    # 4. Subimos
    payload = {
        "message": mensaje,
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode()).decode(),
        "sha": sha if sha else None
    }
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_BUZON}"
    resp = requests.put(url, headers=HEADERS, json=payload)
    return resp.status_code in [200, 201]

def aprender_leccion(error, correccion):
    lecciones, sha = obtener_github(FILE_LECCIONES)
    
    # Si lecciones es None (error de lectura), no intentamos guardar para no romper nada.
    if lecciones is None and sha is None:
         # Excepción: Si es la primera vez (404), obtener_github devuelve [], None. 
         # Si devuelve None, None es error crítico.
         return False

    if lecciones is None: lecciones = [] # Si era 404, iniciamos lista

    nueva = {
        "fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "lo_que_hizo_mal": error,
        "como_debe_hacerlo": correccion
    }
    lecciones.append(nueva)
    
    if enviar_github(FILE_LECCIONES, lecciones[-15:], "LAIA: Nueva lección aprendida"):
        return True
    return False
# ==========================================
# 4. MOTOR DE STOCK
# ==========================================
def calcular_stock_web(df):
    # 1. Si no hay datos, devolvemos dataframes vacíos con estructura correcta
    if df is None or df.empty: 
        return pd.DataFrame(columns=['equipo', 'marca', 'modelo', 'val']), pd.DataFrame(), pd.DataFrame()
    
    df_c = df.copy()
    df_c.columns = df_c.columns.str.lower().str.strip()
    
    # 2. Aseguramos columnas básicas
    cols_necesarias = ['equipo', 'marca', 'modelo', 'estado', 'tipo', 'cantidad', 'destino', 'serie']
    for col in cols_necesarias:
        if col not in df_c.columns: 
            df_c[col] = "n/a"
        else:
            df_c[col] = df_c[col].astype(str).str.lower().str.strip().replace(['nan', 'none', '', 'nan'], 'n/a')
    
    # Cantidad a número
    df_c['cant_n'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(0)

    # --- LÓGICA 1: PERIFÉRICOS (Saldos) ---
    perifericos = ['mouse', 'teclado', 'cable', 'hdmi', 'limpiador', 'cargador', 'toner', 'tinta', 'parlante', 'herramienta']
    mask_perifericos = df_c['equipo'].str.contains('|'.join(perifericos), na=False)
    df_p = df_c[mask_perifericos].copy()

    if not df_p.empty:
        def procesar_saldo(row):
            t = str(row['tipo'])
            c = row['cant_n']
            if any(x in t for x in ['recibido', 'ingreso', 'entrada', 'llegó']): return c
            if any(x in t for x in ['enviado', 'salida', 'despacho', 'egreso', 'envio']): return -c
            return 0
        
        df_p['val'] = df_p.apply(procesar_saldo, axis=1)
        st_res = df_p.groupby(['equipo', 'marca', 'modelo']).agg({'val': 'sum'}).reset_index()
        st_res = st_res[st_res['val'] > 0]
    else:
        # Estructura vacía para evitar que la métrica de Streamlit falle
        st_res = pd.DataFrame(columns=['equipo', 'marca', 'modelo', 'val'])

    # --- LÓGICA 2: BODEGA ---
    bod_res = df_c[df_c['destino'].str.contains('bodega', na=False)].copy()
    if not bod_res.empty:
        # Solo columnas que interesan para la hoja bodega
        cols_b = [c for c in ['equipo', 'marca', 'modelo', 'serie', 'cantidad', 'estado', 'pasillo', 'estante', 'repisa', 'procesador', 'ram', 'disco'] if c in bod_res.columns]
        bod_res = bod_res[cols_b]

    return st_res, bod_res, df_c
# ==========================================
# 5. PROMPT CEREBRO LAIA
# ==========================================
## ROLE: LAIA v2.0 – Auditora de Inventario Multitarea 
SYSTEM_PROMPT = """
## ROLE: LAIA v10.0 – Auditora Técnica Senior (Hardware & Logística)

Eres una experta analista de hardware y gestora de inventarios. Tu prioridad es el razonamiento lógico, la integridad de los datos y la organización de bodega.

### 0. REGLAS DE MAPEO (CRÍTICO):
- **Marca:** Es el fabricante (HP, Dell, LG, Lenovo). **NUNCA** pongas una ciudad o lugar en esta columna.
- **Origen:** Es el lugar de donde viene el equipo (Latacunga, Ibarra, Bodega, etc.).
- **Ubicación de Bodega:** Si el usuario menciona pasillos, estantes o repisas, extrae esa información con precisión para las columnas correspondientes.

Para que el status sea "READY", DEBES tener obligatoriamente estos datos en movimientos "Recibido":
1. **guia:** El número de rastreo.
2. **fecha_llegada:** La fecha en que entró el equipo.
3. **serie:** Fundamental para CPUs y Monitores.
4. No exijas datos si el usuario ya adjunto estos datos.
5. No vuelvas a pedir datos que ya pediste una vez.

- Si falta cualquiera de estos, pon status: "QUESTION" y pide los datos faltantes de forma directa.
- **Solo pon status: "READY" si el usuario explícitamente dice "No tengo la guía" o "No hay serie".**

### 1. RAZONAMIENTO TÉCNICO EXPERTO:
- Evalúa procesadores, RAM y discos por iniciativa propia.
- **Hardware Obsoleto:** Si detectas CPUs de hace más de 10 años (ej. Intel Core de 4ta gen o anterior), clasifícalos como "Obsoleto / Pendiente Chatarrización".
- **Optimización:** Si ves un equipo moderno (>= 10ma gen) con disco mecánico (HDD), añade en 'reporte' tu sugerencia de cambio a SSD.
- Usa la 'MEMORIA DE ERRORES' para evitar fallos previos.

### 2. LOGÍSTICA, STOCK Y BODEGA:
- **Tipo de Movimiento:** Clasifica SIEMPRE como "Recibido" (Entradas) o "Enviado" (Salidas).
- **Destino Stock vs Bodega:** 
    * Si el usuario dice "a stock", el destino es "Stock". (Generalmente para periféricos).
    * Si el usuario dice "a Bodega" o da coordenadas de estantería, el destino es "Bodega". (Generalmente para CPUs, Laptops y Monitores).
- **Lógica de Lotes:** Si el usuario describe varios ítems en un solo mensaje, asume que comparten la misma GUIA, ORIGEN, FECHA y DESTINO.

### 3. GESTIÓN DE MEMORIA (ANTIBORRADO):
- Recibirás el 'BORRADOR ACTUAL'. **NO ELIMINES NADA.**
- **Actualización Masiva:** Si el usuario proporciona un dato (guía, fecha, origen, pasillo) y hay varios ítems que lo necesitan, APLÍCALO A TODOS automáticamente.
- **Sugerencia de Datos:** Eres capaz de sugerir llenar datos faltantes si están vacíos o tienen "N/A". Es obligatorio sugerir Marca y Modelo si están en "N/A".

### 4. FORMATO DE SALIDA (ESTRICTAMENTE JSON):
{
 "status": "READY" o "QUESTION",
 "missing_info": "Mensaje corto pidiendo lo que falte",
 "items": [
 {
  "categoria_item": "Computo/Pantalla/Periferico/Consumible",
  "tipo": "Recibido/Enviado",
  "equipo": "",
  "marca": "",
  "modelo": "",
  "serie": "",
  "cantidad": 1,
  "estado": "Nuevo/Bueno/Obsoleto/Dañado",
  "procesador": "",
  "ram": "",
  "disco": "",
  "reporte": "Tu análisis técnico aquí",
  "origen": "",
  "destino": "",
  "pasillo": "",
  "estante": "",
  "repisa": "",
  "guia": "",
  "fecha_llegada": ""
 }
 ]
}
"""

# ==========================================
# 6. INTERFAZ PRINCIPAL
# ==========================================
if "messages" not in st.session_state: st.session_state.messages = []
if "draft" not in st.session_state: st.session_state.draft = []
if "status" not in st.session_state: st.session_state.status = "NEW"
if "missing_info" not in st.session_state: st.session_state.missing_info = ""

t1, t2, t3 = st.tabs(["💬 Chat Auditor", "📊 Stock Real", "🗑️ Limpieza"])

with t1:
    # 1. Mostrar historial de chat (Visualización)
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # 2. Entrada de Chat
    if prompt := st.chat_input("Dime qué llegó o qué enviaste..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            with st.spinner("LAIA razonando contexto y memoria..."):
                # A) Obtener lecciones de errores previos
                lecciones, _ = obtener_github(FILE_LECCIONES)
                memoria_err = "\n".join([f"- {l['lo_que_hizo_mal']} -> {l['como_debe_hacerlo']}" for l in lecciones]) if lecciones else ""
                
                # B) Obtener el borrador actual en formato texto
                contexto_tabla = json.dumps(st.session_state.draft, ensure_ascii=False) if st.session_state.draft else "[]"
                
                # C) Construir el paquete de mensajes para la IA (HISTORIAL COMPLETO)
                mensajes_api = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "system", "content": f"LECCIONES TÉCNICAS:\n{memoria_err}"},
                    {"role": "system", "content": f"ESTADO ACTUAL DE LA TABLA (REVISA AQUÍ ANTES DE PEDIR DATOS): {contexto_tabla}"}
                ]
                
                # Añadimos los últimos 10 mensajes del chat para que tenga memoria de la plática
                for m in st.session_state.messages[-10:]:
                    mensajes_api.append(m)

                # D) Llamada a OpenAI
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=mensajes_api,
                    temperature=0
                )

                # E) Procesamiento SEGURO del JSON (Escudo contra Error de Contexto)
                raw_txt = response.choices[0].message.content
                res_txt = extraer_json(raw_txt)
                
                if not res_txt or res_txt.strip() == "":
                    st.error("⚠️ LAIA no devolvió un formato válido. Por favor, intenta de nuevo con una instrucción más clara.")
                    st.stop()

                try:
                    res_json = json.loads(res_txt)
                except json.JSONDecodeError:
                    st.error("❌ La respuesta de la IA está corrupta. Intenta refrescar la página.")
                    st.stop()
                
                # F) Actualización de la Tabla
                nuevos_items = res_json.get("items", [])
                if nuevos_items:
                    st.session_state.draft = nuevos_items
                
                st.session_state.status = res_json.get("status", "READY")
                st.session_state.missing_info = res_json.get("missing_info", "")

                # G) Respuesta de LAIA en el chat
                msg_laia = f"🤖 {st.session_state.missing_info}" if st.session_state.missing_info else "✅ Todo registrado. He actualizado la tabla."
                with st.chat_message("assistant"):
                    st.markdown(msg_laia)
                st.session_state.messages.append({"role": "assistant", "content": msg_laia})
                
                st.rerun()

        except Exception as e:
            st.error(f"❌ Fallo crítico de IA: {str(e)}")

    # 3. Tabla de Edición en Vivo (Vista de Bodega y Stock)
    if st.session_state.draft:
        st.divider()
        st.subheader("📊 Borrador de Movimientos (Antes de Guardar)")
        
        df_editor = pd.DataFrame(st.session_state.draft)
        
        # Columnas obligatorias incluyendo las de BODEGA y REPORTE TÉCNICO
        cols_base = [
            "equipo", "marca", "modelo", "serie", "cantidad", "estado", 
            "tipo", "origen", "destino", "pasillo", "estante", "repisa", 
            "guia", "fecha_llegada", "ram", "disco", "procesador", "reporte"
        ]
        
        # Aseguramos que existan todas las columnas
        for c in cols_base:
            if c not in df_editor.columns: df_editor[c] = ""
        
        # Reordenar y limpiar visualmente para el usuario
        df_editor = df_editor.reindex(columns=cols_base).fillna("N/A")

        edited_df = st.data_editor(
            df_editor, 
            num_rows="dynamic", 
            use_container_width=True,
            key="editor_pro_v10"
        )
        
        # Guardar cambios manuales si el usuario edita la celda directamente
        if not df_editor.equals(edited_df):
            st.session_state.draft = edited_df.to_dict("records")

        # 4. Botones de Acción
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("🚀 GUARDAR EN HISTÓRICO", type="primary"):
                with st.spinner("Sincronizando con GitHub..."):
                    # Añadir marca de tiempo de registro real
                    hora_ec = (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                    for d in st.session_state.draft: 
                        d["fecha_registro"] = hora_ec

                    if enviar_github(FILE_BUZON, st.session_state.draft, "Registro LAIA - Bodega y Stock"):
                        st.success("✅ Guardado con éxito.")
                        st.session_state.draft = []
                        st.session_state.messages = []
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("No se pudo subir a GitHub. Revisa la conexión.")
        with c2:
            if st.button("🗑️ Descartar Todo"):
                st.session_state.draft = []
                st.session_state.messages = []
                st.rerun()
with t2:
    st.subheader("📊 Control de Stock e Historial")
     
    # 1. Botón para sincronizar
    if st.button("🔄 Sincronizar Datos de GitHub"):
        st.rerun()

    # 2. Obtenemos el histórico real
    hist, _ = obtener_github(FILE_HISTORICO)
     
    if hist:
        # --- AQUÍ CREAMOS df_h PARA QUE NO DE NAMEERROR ---
        df_h_raw = pd.DataFrame(hist)
        
        # 3. Calculamos stock usando la nueva función v10.0
        # La función nos devuelve: saldos, bodega e historial limpio
        st_res, bod_res, df_h = calcular_stock_web(df_h_raw)
         
        # 4. Mostramos métricas
        k1, k2 = st.columns(2)
        # Usamos 'val' para la métrica
        total_stock = int(st_res['val'].sum()) if not st_res.empty else 0
        k1.metric("📦 Periféricos en Stock", total_stock)
        k2.metric("🚚 Movimientos Totales", len(df_h))

        # --- GENERACIÓN DEL EXCEL MULTI-HOJA ---
        import io
        buffer = io.BytesIO()
        
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            # HOJA 1: Historial Completo
            df_h.to_excel(writer, index=False, sheet_name='Enviados y Recibidos')
            
            # HOJA 2: Stock Saldos
            if not st_res.empty:
                st_res_excel = st_res.copy()
                st_res_excel.columns = ['equipo', 'marca', 'modelo', 'variacion']
                st_res_excel.to_excel(writer, index=False, sheet_name='Stock (Saldos)')
            
            # HOJA 3: BODEGA
            if not bod_res.empty:
                bod_res.to_excel(writer, index=False, sheet_name='BODEGA')
         
        st.download_button(
            label="📥 DESCARGAR EXCEL SINCRONIZADO (3 HOJAS)",
            data=buffer.getvalue(),
            file_name=f"Inventario_Jaher_{datetime.datetime.now().strftime('%d_%m_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary" 
        )
        # ----------------------------------------

        # 5. Mostrar la tabla en la web
        st.write("### 📜 Últimos Movimientos en el Histórico")
        st.dataframe(df_h.tail(20), use_container_width=True) 
         
    else:
        st.warning("⚠️ No se encontraron datos en el histórico. Verifica el archivo en GitHub.")
with t3:
    st.subheader("🗑️ Limpieza Inteligente")

    txt_borrar = st.text_input("¿Qué deseas eliminar?")

    if st.button("🔥 EJECUTAR BORRADO"):
        if txt_borrar:
            try:
                p_db = (
                    "Actúa como DBA. "
                    "COLUMNAS: [equipo, marca, serie, estado, destino]. "
                    "ORDEN: " + txt_borrar +
                    "\nRESPONDE SOLO JSON: "
                    "{\"accion\":\"borrar_todo\"} "
                    "o "
                    "{\"accion\":\"borrar_filtro\",\"columna\":\"...\",\"valor\":\"...\"}"
                )

                resp = client.responses.create(
                    model="gpt-4o-mini",
                    input=p_db
                )

                texto = resp.output_text
                order = json.loads(extraer_json(texto))

                if enviar_github(FILE_BUZON, order):
                    st.success("✅ Orden enviada.")
                    st.json(order)

            except Exception as e:
                st.error("Error: " + str(e))
                st.sidebar.divider()
                st.sidebar.subheader("🎓 Entrenar a LAIA")
with st.sidebar.expander("¿LAIA cometió un error? Enséñale"):
    error_ia = st.text_area("¿Qué hizo mal LAIA?", placeholder="Ej: Me pidió fecha para un envío...")
    solucion_ia = st.text_area("¿Cómo debe actuar?", placeholder="Ej: Nunca pidas fecha si el tipo es 'Enviado'...")
    if st.button("🧠 Guardar Lección"):
        if error_ia and solucion_ia:
            if aprender_leccion(error_ia, solucion_ia):
                st.success("Lección guardada. LAIA no volverá a cometer ese error.")
                time.sleep(2)
                st.rerun()
            else:
                st.error("No se pudo guardar en GitHub.")

if st.sidebar.button("🧹 Borrar Chat"):
    st.session_state.messages = []
    st.session_state.draft = None
    st.rerun()
