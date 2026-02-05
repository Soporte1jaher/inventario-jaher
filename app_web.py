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
    if df.empty: return pd.DataFrame(), pd.DataFrame()
    
    df_c = df.copy()
    # 1. Normalización total: todo a minúsculas y sin espacios locos
    df_c.columns = df_c.columns.str.lower().str.strip()
    
    # 2. Aseguramos que las columnas existan y limpiamos los "N/A"
    for col in ['equipo', 'marca', 'modelo', 'estado', 'tipo', 'cantidad']:
        if col not in df_c.columns: 
            df_c[col] = "n/a"
        else:
            # Convertimos todo a texto, quitamos espacios y estandarizamos "n/a"
            df_c[col] = df_c[col].astype(str).str.lower().str.strip().replace(['nan', 'none', '', 'nan'], 'n/a')
    
    # 3. Cantidad a número (si falla pone 0)
    df_c['cant_n'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(0)

    def procesar_fila(row):
        eq = row['equipo']
        tipo = row['tipo']
        est = row['estado']
        cant = row['cant_n']

        # Detección inteligente de Movimiento
        es_entrada = any(x in tipo for x in ['recibido', 'ingreso', 'entrada', 'llegó', 'compra', 'stock'])
        es_salida = any(x in tipo for x in ['enviado', 'salida', 'despacho', 'egreso', 'envié', 'envio', 'entregado'])

        # Lógica de Periféricos (No importa el estado técnico)
        perifericos = ['mouse', 'teclado', 'cable', 'hdmi', 'limpiador', 'cargador', 'toner', 'tinta', 'herramienta']
        if any(p in eq for p in perifericos):
            if es_entrada: return cant
            if es_salida: return -cant
            return 0 

        # Lógica de Equipos Críticos (Laptops/Monitores)
        # Si está dañado o es chatarra, no suma al stock disponible
        if any(x in est for x in ['dañ', 'obs', 'chatarra', 'malo']):
            return 0
        
        if es_entrada: return cant
        if es_salida: return -cant
        return 0

    # Aplicamos la lógica a cada fila
    df_c['val'] = df_c.apply(procesar_fila, axis=1)
    
    # 4. AGRUPACIÓN MAESTRA
    # Agrupamos SOLO por equipo, marca y modelo para que los "Enviados" 
    # encuentren a los "Recibidos" y se resten.
    resumen = df_c.groupby(['equipo', 'marca', 'modelo']).agg({'val': 'sum'}).reset_index()
    
    # Renombramos para el Excel de saldos
    resumen.columns = ['equipo', 'marca', 'modelo', 'variacion']
    
    # Creamos stock_real para las métricas de la web (usando el nombre 'val')
    stock_real = resumen.copy()
    stock_real.columns = ['equipo', 'marca', 'modelo', 'val']
    stock_real = stock_real[stock_real['val'] > 0]
    
    return stock_real, df_c

# ==========================================
# 5. PROMPT CEREBRO LAIA
# ==========================================
## ROLE: LAIA v2.0 – Auditora de Inventario Multitarea 
SYSTEM_PROMPT = """
## ROLE: LAIA v9.0 – Auditora Técnica Senior (Hardware & Logística)

Eres una experta analista de hardware y gestora de inventarios. Tu prioridad es el razonamiento lógico y la integridad de los datos.
### 0. REGLAS DE MAPEO (CRÍTICO):
- **Marca:** Es el fabricante (HP, Dell, LG, Lenovo). **NUNCA** pongas una ciudad o lugar en esta columna.
- **Origen:** Es el lugar de donde viene el equipo (Latacunga, Ibarra, Bodega, etc.).

Para que el status sea "READY", DEBES tener obligatoriamente estos datos en movimientos "Recibido":
1. **guia:** El número de rastreo.
2. **fecha_llegada:** La fecha en que entró el equipo.
3. **serie:** Fundamental para CPUs y Monitores.
4. No exijas datos si el usuario ya adjunto estos datos.
5. No vuelvas a pedir datos que ya pediste una vez.
- Si falta cualquiera de estos, pon status: "QUESTION" y pide los datos faltantes de forma directa.
- **Solo pon status: "READY" si el usuario explícitamente dice "No tengo la guía" o "No hay serie".** De lo contrario, asume que se le olvidó y pídela.


### 1. RAZONAMIENTO TÉCNICO EXPERTO:
- Evalúa procesadores, RAM y discos por iniciativa propia.
- **Hardware Obsoleto:** Si detectas CPUs de hace más de 10 años (ej. Intel Core de 4ta gen o anterior), clasifícalos como "Obsoleto / Pendiente Chatarrización".
- **Optimización:** Si ves un equipo moderno (>= 10ma gen) con disco mecánico (HDD), añade en 'reporte' tu sugerencia de cambia a SSD que veas conveniente.
- Usa la 'MEMORIA DE ERRORES' para evitar fallos de formato o lógica cometidos anteriormente.

### 2. LOGÍSTICA E INVENTARIO (REGLAS CRÍTICAS):
- **Tipo de Movimiento:** Clasifica SIEMPRE como "Recibido" (Entradas) o "Enviado" (Salidas). Usa estas palabras exactas para que el motor de stock funcione.
- **Destino Stock:** Si el usuario dice "a stock", "llega a bodega" o similar, pon automáticamente "Stock" en la columna 'destino'.
- **Lógica de Lotes:** Si el usuario describe varios ítems en un solo mensaje, asume que comparten la misma GUIA, ORIGEN, FECHA y DESTINO. No los separes a menos que se indique lo contrario.


### 3. GESTIÓN DE MEMORIA (ANTIBORRADO):
- Recibirás el 'BORRADOR ACTUAL'. 
- **NO ELIMINES NADA:** Si el usuario añade algo nuevo, mantén lo que ya estaba y agrégalo a la lista.
- **Actualización Masiva:** Si el usuario proporciona un dato (como guía, fecha u origen) y hay varios ítems en la tabla que necesitan ese dato, APLÍCALO A TODOS los ítems afectados automáticamente.
- **Validación de N/A:** Si un campo tiene "N/A", se considera LLENO y VÁLIDO. No lo marques como faltante.
Excepción: Si se trata de "marca" y "modelo" sugiere al usuario poner estos datos.
- **Prioridad de la Tabla:** Antes de responder, revisa cada fila de la tabla. Si todos los campos obligatorios tienen información (aunque sea N/A), el status DEBE ser "READY".

### 4. FORMATO DE SALIDA (ESTRICTAMENTE JSON):
{
 "status": "READY" o "QUESTION",
 "missing_info": "Mensaje corto pidiendo lo que falte (guía, origen, serie, etc.)",
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
   "almacenamiento": "",
   "reporte": "Tu análisis técnico aquí",
   "origen": "",
   "destino": "",
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
    # 1. Historial de chat (Visualización en pantalla)
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # 2. Entrada de Chat
    if prompt := st.chat_input("Dime qué llegó o qué enviaste..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            with st.spinner("LAIA analizando contexto y memoria..."):
                # A) Cargar lecciones aprendidas
                lecciones, _ = obtener_github(FILE_LECCIONES)
                memoria_err = "\n".join([f"- {l['lo_que_hizo_mal']} -> {l['como_debe_hacerlo']}" for l in lecciones]) if lecciones else ""
                
                # B) Cargar estado actual de la tabla
                contexto_tabla = json.dumps(st.session_state.draft, ensure_ascii=False) if st.session_state.draft else "[]"
                
                # C) CONSTRUCCIÓN DE MEMORIA TOTAL PARA LA API
                # Empezamos con el Sistema y la Tabla
                mensajes_api = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "system", "content": f"MEMORIA TÉCNICA: {memoria_err}"},
                    {"role": "system", "content": f"ESTADO ACTUAL DE LA TABLA: {contexto_tabla}"}
                ]
                
                # AÑADIMOS EL HISTORIAL DE LA CONVERSACIÓN (Últimos 10 mensajes)
                # Esto evita que pida cosas que ya se dijeron en el chat
                for m in st.session_state.messages[-10:]:
                    mensajes_api.append(m)

                # D) Llamada a la Inteligencia
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=mensajes_api,
                    temperature=0
                )

                res_txt = extraer_json(response.choices[0].message.content)
                res_json = json.loads(res_txt)
                
                # E) Actualización inteligente del borrador
                nuevos_items = res_json.get("items", [])
                if nuevos_items:
                    st.session_state.draft = nuevos_items
                
                st.session_state.status = res_json.get("status", "READY")
                st.session_state.missing_info = res_json.get("missing_info", "")

                # F) Respuesta de LAIA
                msg_laia = f"🤖 {st.session_state.missing_info}" if st.session_state.missing_info else "✅ Todo registrado. He actualizado la tabla con el nuevo contexto."
                with st.chat_message("assistant"):
                    st.markdown(msg_laia)
                
                st.session_state.messages.append({"role": "assistant", "content": msg_laia})
                st.rerun()

        except Exception as e:
            st.error(f"❌ Error de Contexto: {e}")

    # 3. Tabla de Edición en Vivo
    if st.session_state.draft:
        st.divider()
        st.subheader("📊 Borrador de Movimientos (Antes de Guardar)")
        
        df_editor = pd.DataFrame(st.session_state.draft)
        
        # Columnas obligatorias (Aseguramos que 'destino' y 'ram/disco' sean visibles)
        cols_base = [
            "equipo", "marca", "modelo", "serie", "cantidad", "estado", 
            "tipo", "origen", "destino", "guia", "fecha_llegada", 
            "ram", "disco", "procesador", "reporte"
        ]
        
        for c in cols_base:
            if c not in df_editor.columns: df_editor[c] = ""
        
        # Reordenar y limpiar visualmente
        df_editor = df_editor.reindex(columns=cols_base).fillna("N/A")

        edited_df = st.data_editor(
            df_editor, 
            num_rows="dynamic", 
            use_container_width=True,
            key="editor_principal_v9"
        )
        
        # Sincronizar cambios manuales del usuario con el estado de la app
        if not df_editor.equals(edited_df):
            st.session_state.draft = edited_df.to_dict("records")

        # 4. Botones de Acción Final
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("🚀 GUARDAR EN HISTÓRICO", type="primary"):
                with st.spinner("Sincronizando con GitHub..."):
                    hora_ec = (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                    for d in st.session_state.draft: 
                        d["fecha_registro"] = hora_ec

                    if enviar_github(FILE_BUZON, st.session_state.draft, "Registro LAIA - Memoria Contextual"):
                        st.success("✅ Guardado correctamente.")
                        st.session_state.draft = []
                        st.session_state.messages = []
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Error al subir a GitHub. Revisa el Token.")
        with c2:
            if st.button("🗑️ Descartar Borrador"):
                st.session_state.draft = []
                st.session_state.messages = []
                st.rerun()
with t2:
    st.subheader("📊 Control de Stock e Historial")
    
    # 1. Botón para forzar la sincronización (limpia el caché)
    if st.button("🔄 Sincronizar Datos de GitHub"):
        st.rerun()

    # 2. Obtenemos el histórico real
    hist, _ = obtener_github(FILE_HISTORICO)
    
    if hist:
        df_h = pd.DataFrame(hist)
        # Normalizamos columnas
        df_h.columns = df_h.columns.str.lower().str.strip()
        
        # 3. Calculamos stock (usando tu función)
        st_res, st_det = calcular_stock_web(df_h)
        
        # 4. Mostramos métricas
        k1, k2 = st.columns(2)
        k1.metric("📦 Stock Total", int(st_res['val'].sum()) if not st_res.empty else 0)
        k2.metric("🚚 Total Movimientos", len(df_h))

        # --- AQUÍ ESTÁ LA MAGIA PARA EL EXCEL ---
        import io
        buffer = io.BytesIO()
        # Creamos el Excel en la memoria del navegador con los datos de historico.json
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
          df_h.to_excel(writer, index=False, sheet_name='Enviados y Recibidos') # Cambié el nombre para que sea más claro
          if not st_res.empty:
        # Aquí forzamos que la columna se llame 'variacion' en el Excel
            st_res_excel = st_res.copy()
            st_res_excel.columns = ['equipo', 'marca', 'modelo', 'variacion']
            st_res_excel.to_excel(writer, index=False, sheet_name='Stock (Saldos)')
        
        st.download_button(
            label="📥 DESCARGAR EXCEL SINCRONIZADO",
            data=buffer.getvalue(),
            file_name=f"Inventario_Jaher_{datetime.datetime.now().strftime('%d_%m_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary" # Lo pone en color verde/destacado
        )
        # ----------------------------------------

        # 5. Mostrar la tabla en la web para verificar
        st.write("### 📜 Últimos Movimientos en el Histórico")
        st.dataframe(df_h.tail(20), use_container_width=True) # Muestra los últimos 20
        
    else:
        st.warning("⚠️ No se encontraron datos en el histórico. Verifica que historico.json en GitHub tenga información.")
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
