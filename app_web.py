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
# 3. FUNCIONES AUXILIARES (BACKEND & GITHUB)
# ==========================================

# --- [BLOQUE DE CORREO - RESERVADO] ---
# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# def enviar_correo_outlook(destinatario, asunto, cuerpo):
#     try:
#         remitente = st.secrets["EMAIL_USER"]
#         password = st.secrets["EMAIL_PASS"]
#         msg = MIMEMultipart()
#         msg['From'] = remitente
#         msg['To'] = destinatario
#         msg['Subject'] = asunto
#         msg.attach(MIMEText(cuerpo, 'plain'))
#         server = smtplib.SMTP('smtp.office365.com', 587)
#         server.starttls()
#         server.login(remitente, password)
#         server.send_message(msg)
#         server.quit()
#         return True, "OK"
#     except Exception as e:
#         return False, str(e)

# --- 1. UTILIDADES DE GITHUB (NÚCLEO) ---

def obtener_github(archivo):
    """ Descarga y decodifica archivos JSON desde GitHub """
    timestamp = int(time.time())
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}?t={timestamp}"  
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            d = resp.json()
            contenido = base64.b64decode(d['content']).decode('utf-8')
            try:
                return json.loads(contenido), d['sha']
            except json.JSONDecodeError:
                st.error(f"⛔ Error: El archivo {archivo} está corrupto.")
                return None, None
        elif resp.status_code == 404:
            return [], None
        return None, None
    except Exception as e:
        st.error(f"❌ Error de conexión GitHub: {str(e)}")
        return None, None

def enviar_github_directo(archivo, datos, mensaje="LAIA Update"):
    """ ESTA FUNCIÓN SOBREESCRIBE EL ARCHIVO (Para pedidos y configuración) """
    _, sha = obtener_github(archivo)
    payload = {
        "message": mensaje,
        "content": base64.b64encode(json.dumps(datos, indent=4).encode()).decode(),
        "sha": sha if sha else None
    }
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}"
    resp = requests.put(url, headers=HEADERS, json=payload)
    return resp.status_code in [200, 201]

def solicitar_busqueda_glpi(serie):
    """ Ahora usa la función de sobreescribir para no crear listas locas """
    pedido = {
        "serie_a_buscar": serie,
        "info": "",
        "estado": "pendiente"
    }
    return enviar_github_directo("pedido.json", pedido, f"LAIA: Solicitud serie {serie}")

def revisar_respuesta_glpi():
    """ Lee el archivo de pedido para ver si la PC local ya respondió """
    contenido, _ = obtener_github("pedido.json")
    # Validamos que el contenido sea un diccionario antes de usar .get()
    if isinstance(contenido, dict) and contenido.get("estado") == "completado":
        return contenido
    return None
# --- 3. AYUDANTES DE IA Y APRENDIZAJE ---

def extraer_json(texto):
    """ Limpia la respuesta de la IA para obtener solo el JSON """
    try:
        texto = texto.replace("```json", "").replace("```", "").strip()
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        return texto[inicio:fin].strip() if inicio != -1 else ""
    except:
        return ""

def aprender_leccion(error, correccion):
    """ Guarda errores previos para que la IA no los repita """
    lecciones, _ = obtener_github(FILE_LECCIONES)
    if lecciones is None: lecciones = []
    
    nueva = {
        "fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "lo_que_hizo_mal": error,
        "como_debe_hacerlo": correccion
    }
    lecciones.append(nueva)
    # Guardamos solo las últimas 15 lecciones para no saturar el prompt
    return enviar_github(FILE_LECCIONES, lecciones[-15:], "LAIA: Nueva lección aprendida")

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

### 4. REGLA DE HARDWARE EN BODEGA:
- Aunque un equipo (CPU, Laptop, Servidor) vaya a "Bodega", es OBLIGATORIO registrar su Procesador, RAM y Disco.
- No des por completado el registro (status: READY) si faltan estos datos técnicos para equipos de computo.

### 6. REGLA DE INTERACCIÓN HUMANA (CRÍTICO):
- Si recibes cualquier consulta ajena a tu labor, responde de forma amable y veraz sin extender la conversación y luego retoma tu desempeño principal.
- Si el usuario menciona temas personales, emocionales o ajenos al ámbito laboral (por ejemplo: “me dejó mi novia”), responde con empatía breve y respetuosa, sin profundizar ni asumir un rol de consejería, después de una sola frase empática, redirige la conversación de forma clara al objetivo laboral, solicitando una instrucción o requerimiento concreto.
- NUNCA uses emojis adicionales, solo los técnicos permitidos.
- Mantén un tono burocrático, eficiente y orientado a datos.

### 5. FORMATO DE SALIDA (ESTRICTAMENTE JSON):
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
  # 1. Mostrar historial de chat
  for m in st.session_state.messages:
    with st.chat_message(m["role"]):
      st.markdown(m["content"])

  # 2. Entrada de Chat
  if prompt := st.chat_input("Dime qué llegó o qué enviaste..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
      st.markdown(prompt)

    try:
      with st.spinner("LAIA auditando información..."):
        lecciones, _ = obtener_github(FILE_LECCIONES)
        memoria_err = "\n".join([f"- {l['lo_que_hizo_mal']} -> {l['como_debe_hacerlo']}" for l in lecciones]) if lecciones else ""
        contexto_tabla = json.dumps(st.session_state.draft, ensure_ascii=False) if st.session_state.draft else "[]"
         
        mensajes_api = [
          {"role": "system", "content": SYSTEM_PROMPT},
          {"role": "system", "content": f"LECCIONES TÉCNICAS:\n{memoria_err}"},
          {"role": "system", "content": f"ESTADO ACTUAL DE LA TABLA: {contexto_tabla}"}
        ]
         
        for m in st.session_state.messages[-10:]:
          mensajes_api.append(m)

        response = client.chat.completions.create(
          model="gpt-4o-mini",
          messages=mensajes_api,
          temperature=0
        )

        # --- LÓGICA ANTI-TRABA (Blindaje de JSON) ---
        raw_content = response.choices[0].message.content
        res_txt = extraer_json(raw_content)
        
        try:
            # Intentamos leer el JSON normal
            res_json = json.loads(res_txt)
        except Exception:
            # Si la IA no mandó JSON (ej: un saludo frío o rechazo de charla), 
            # forzamos este formato para que el código siga funcionando.
            res_json = {
                "status": "QUESTION",
                "missing_info": raw_content.strip(), # Aquí va el mensaje frío de la IA
                "items": st.session_state.draft      # Mantenemos lo que ya estaba en la tabla
            }
         
        st.session_state.draft = res_json.get("items", [])
        st.session_state.status = res_json.get("status", "READY")
        st.session_state.missing_info = res_json.get("missing_info", "")

        # E) Respuesta de LAIA (Adaptada para respuestas frías)
        if st.session_state.status == "QUESTION":
          # Si la IA está pidiendo algo o respondiendo un saludo, se muestra directo y frío
          msg_laia = f"🤖 {st.session_state.missing_info}"
        else:
          # Solo cuando ya reconoció hardware y todo está completo
          msg_laia = "🤖 ✅ **AUDITORÍA LISTA:** Todos los campos obligatorios están llenos."
         
        with st.chat_message("assistant"):
          st.markdown(msg_laia)
        st.session_state.messages.append({"role": "assistant", "content": msg_laia})
        st.rerun()

    except Exception as e:
      st.error(f"❌ Fallo crítico de IA: {str(e)}")

    # 3. Tabla y Botones GLPI
    if st.session_state.draft:
        st.divider()
        st.subheader("📊 Borrador de Movimientos")
        
        df_editor = pd.DataFrame(st.session_state.draft)
        cols_base = ["equipo", "marca", "modelo", "serie", "cantidad", "estado", "tipo", "origen", "destino", "pasillo", "estante", "repisa", "guia", "fecha_llegada", "ram", "disco", "procesador", "reporte"]
        for c in cols_base:
            if c not in df_editor.columns: df_editor[c] = ""
        
        df_editor = df_editor.reindex(columns=cols_base).fillna("N/A")
        edited_df = st.data_editor(df_editor, num_rows="dynamic", use_container_width=True, key="editor_v11")
        
        if not df_editor.equals(edited_df):
            st.session_state.draft = edited_df.to_dict("records")

        # --- SECCIÓN GLPI MEJORADA ---
        col_glpi1, col_glpi2 = st.columns([2, 1])
        with col_glpi1:
            if st.button("🔍 SOLICITAR BÚSQUEDA EN OFICINA"):
                serie_valida = next((item.get('serie') for item in st.session_state.draft if item.get('serie') and item.get('serie') != "N/A"), None)
                if serie_valida:
                    if solicitar_busqueda_glpi(serie_valida):
                        st.toast(f"Pedido enviado para serie {serie_valida}", icon="📡")
                        time.sleep(10) # Aumentamos a 10 segundos para GitHub
                        st.rerun()
                else:
                    st.warning("⚠️ No hay una serie válida para buscar.")
        
        with col_glpi2:
            if st.button("🔄 REVISAR Y AUTORELLENAR"):
                res_glpi = revisar_respuesta_glpi()
                
                # Si la PC ya respondió y mandó la ficha técnica (specs)
                if res_glpi and res_glpi.get("estado") == "completado":
                    specs_oficina = res_glpi.get("specs", {})
                    serie_buscada = res_glpi.get("serie")
                    
                    # Buscamos la fila en la tabla y la actualizamos
                    encontrado = False
                    nuevo_borrador = []
                    
                    for item in st.session_state.draft:
                        if item.get("serie") == serie_buscada:
                            # ACTUALIZAMOS LOS CAMPOS CON LO QUE MANDÓ LA PC
                            item["marca"] = specs_oficina.get("marca", item["marca"])
                            item["modelo"] = specs_oficina.get("modelo", item["modelo"])
                            item["ram"] = specs_oficina.get("ram", item["ram"])
                            item["disco"] = specs_oficina.get("disco", item["disco"])
                            item["procesador"] = specs_oficina.get("procesador", item["procesador"])
                            item["reporte"] = specs_oficina.get("reporte", item["reporte"])
                            encontrado = True
                        nuevo_borrador.append(item)
                    
                    if encontrado:
                        st.session_state.draft = nuevo_borrador
                        st.success(f"✨ ¡Datos de serie {serie_buscada} cargados en la tabla!")
                        time.sleep(1)
                        st.rerun() # Refrescamos para que se vea el cambio
                else:
                    st.info("⏳ Esperando que la PC de la oficina envíe la ficha técnica...")


        # 4. Botones de Acción
        c1, c2 = st.columns([1, 4])
        with c1:
            # BLOQUEO DE GUARDADO SI NO ESTÁ READY
            if st.session_state.status == "READY":
                if st.button("🚀 GUARDAR EN HISTÓRICO", type="primary"):
                    hora_ec = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                    for d in st.session_state.draft: d["fecha_registro"] = hora_ec
                    if enviar_github(FILE_BUZON, st.session_state.draft, "Registro LAIA"):
                        st.success("✅ Guardado.")
                        st.session_state.draft = []
                        st.session_state.messages = []
                        st.rerun()
            else:
                st.button("🚀 GUARDAR (BLOQUEADO)", disabled=True, help="Completa todos los campos para guardar.")
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
    st.subheader("🗑️ Limpieza Inteligente con Análisis de Historial")
    st.info("Ejemplo: 'Borra la laptop ProBook', 'Limpia lo que llegó de Latacunga'")

    txt_borrar = st.text_input("¿Qué deseas eliminar de la base de datos?", placeholder="Escribe tu instrucción aquí...")

    if st.button("🔥 BUSCAR Y ELIMINAR", type="secondary"):
        if txt_borrar:
            try:
                with st.spinner("LAIA analizando historial para identificar el objetivo..."):
                    # 1. Obtenemos el historial real para darle contexto a la IA
                    hist, _ = obtener_github(FILE_HISTORICO)
                    contexto_breve = json.dumps(hist[-30:], ensure_ascii=False) if hist else "[]" # Últimos 30 registros

                    p_db = f"""
                    Actúa como DBA Senior. Tu objetivo es generar un comando de borrado preciso.
                    REVISA EL HISTORIAL ACTUAL PARA ENCONTRAR COINCIDENCIAS.

                    HISTORIAL ACTUAL (Muestra): {contexto_breve}

                    INSTRUCCIÓN DEL USUARIO: "{txt_borrar}"

                    REGLAS DE SALIDA:
                    1. Si es algo general (ej: 'borra todo'): {{"accion": "borrar_todo"}}
                    2. Si es algo específico (ej: 'borra las laptops', 'borra la serie 123', 'borra lo de HP'):
                       Busca en el historial la columna que mejor coincida (equipo, marca, modelo, serie, origen, destino).
                       Genera: {{"accion": "borrar_filtro", "columna": "NOMBRE_COLUMNA", "valor": "VALOR_EXACTO"}}

                    RESPONDE ÚNICAMENTE EL JSON.
                    """

                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "system", "content": p_db}],
                        temperature=0
                    )

                    texto_ia = response.choices[0].message.content.strip()
                    inicio, fin = texto_ia.find("{"), texto_ia.rfind("}") + 1
                    order = json.loads(texto_ia[inicio:fin])

                    if enviar_github(FILE_BUZON, order, "Orden de Borrado Inteligente"):
                        st.success(f"✅ Orden de borrado generada con éxito.")
                        st.json(order)
                        st.warning("El script local eliminará estos registros en unos segundos.")
            except Exception as e:
                st.error(f"Error: {e}")
def conectar_glpi_jaher():
    config, _ = obtener_github("config_glpi.json")
    if not config or "url_glpi" not in config:
        return None, "Fallo: El link en GitHub no existe."
    
    base_url = config["url_glpi"]
    session = requests.Session()
    
    # HEADERS MÁS REALES (Copiados de un Chrome real)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9',
        'Origin': base_url,
        'Referer': f"{base_url}/front/login.php"
    })

    usuario = "soporte1"
    clave = "Cpktnwt1986@*."

    try:
        # 1. Obtener Token CSRF
        login_page = session.get(f"{base_url}/front/login.php", timeout=10)
        import re
        csrf_match = re.search(r'name="_glpi_csrf_token" value="([^"]+)"', login_page.text)
        csrf_token = csrf_match.group(1) if csrf_match else ""

        # 2. Intentar Login
        payload = {
            'noAuto': '0',
            'login_name': usuario,
            'login_password': clave,
            '_glpi_csrf_token': csrf_token,
            'submit': 'Enviar'
        }
        
        response = session.post(f"{base_url}/front/login.php", data=payload, allow_redirects=True)

        # 3. VERIFICACIÓN DE DIAGNÓSTICO
        if session.cookies.get('glpi_session'):
            # Si entramos, manejamos el perfil
            if "selectprofile.php" in response.url:
                p_match = re.search(r'profiles_id=([0-9]+)[^>]*>Soporte Técnico', response.text, re.IGNORECASE)
                p_id = p_match.group(1) if p_match else "4"
                session.get(f"{base_url}/front/selectprofile.php?profiles_id={p_id}")
            return session, base_url
        else:
            # MOSTRAR QUÉ DICE LA PÁGINA (Para saber si es un error de clave, captcha o bloqueo)
            if "CSRF" in response.text: error = "Error de Token CSRF (Seguridad)"
            elif "identificador o la contraseña son incorrectos" in response.text: error = "Usuario o Clave mal escritos"
            elif "Javascript" in response.text: error = "GLPI exige navegador con Javascript (Bloqueo de bot)"
            else: error = "Bloqueo desconocido por el Firewall de Jaher"
            return None, f"Fallo: {error}"

    except Exception as e:
        return None, f"Error de red: {str(e)}"

def consultar_datos_glpi(serie):
    """ Busca datos navegando en el panel global (ya que la API está deshabilitada) """
    session, base_url = conectar_glpi_jaher()
    if not session:
        return None
    
    # Buscamos en el buscador global de GLPI
    url_busqueda = f"{base_url}/front/allassets.php?contains%5B0%5D={serie}&itemtype=all"
    
    try:
        resp = session.get(url_busqueda, timeout=10)
        if serie.lower() in resp.text.lower():
            # Si la serie aparece en el HTML, es que el equipo existe
            return {"status": "Encontrado", "msg": f"Equipo {serie} detectado en GLPI"}
        return None
    except:
        return None
