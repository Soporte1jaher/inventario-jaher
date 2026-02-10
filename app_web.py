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

def enviar_github(archivo, datos_nuevos, mensaje="Actualización LAIA"):
    """ Agrega datos a una lista existente en GitHub (APPEND) """
    contenido_actual, sha = obtener_github(archivo)
    if contenido_actual is None: contenido_actual = []
    
    # Si datos_nuevos es lista, extendemos; si es dict, append
    if isinstance(datos_nuevos, list):
        contenido_actual.extend(datos_nuevos)
    else:
        contenido_actual.append(datos_nuevos)
    
    payload = {
        "message": mensaje,
        "content": base64.b64encode(json.dumps(contenido_actual, indent=4).encode()).decode(),
        "sha": sha if sha else None
    }
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}"
    resp = requests.put(url, headers=HEADERS, json=payload)
    return resp.status_code in [200, 201]

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

def extraer_json(texto_completo):
    """ Separa el texto hablado del bloque JSON """
    try:
        inicio = texto_completo.find("{")
        fin = texto_completo.rfind("}") + 1
        
        if inicio != -1:
            texto_hablado = texto_completo[:inicio].strip()
            json_puro = texto_completo[inicio:fin].strip()
            return texto_hablado, json_puro
        return texto_completo.strip(), ""
    except:
        return texto_completo.strip(), ""

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
    if df is None or df.empty: 
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    df_c = df.copy()
    df_c.columns = df_c.columns.str.lower().str.strip()
    
    # Limpieza estricta
    for col in df_c.columns:
        df_c[col] = df_c[col].astype(str).str.lower().str.strip()
    
    df_c['cant_n'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(0)

    # Definiciones de tipos
    perifericos_list = ['mouse', 'teclado', 'cable', 'hdmi', 'limpiador', 'cargador', 'toner', 'tinta', 'parlante', 'herramienta']
    
    # Máscaras Booleanas (Filtros Reales)
    es_periferico = df_c['equipo'].str.contains('|'.join(perifericos_list), na=False)
    es_dañado = df_c['estado'].str.contains('dañado|obsoleto|chatarrización', na=False)
    es_destino_bodega = df_c['destino'] == 'bodega'

    # --- 1. STOCK (Solo Periféricos para balance) ---
    df_p = df_c[es_periferico].copy()
    if not df_p.empty:
        def procesar_saldo(row):
            t = row['tipo']
            if any(x in t for x in ['recibido', 'ingreso', 'entrada', 'llegó']): return row['cant_n']
            if any(x in t for x in ['enviado', 'salida', 'despacho', 'egreso', 'envio']): return -row['cant_n']
            return 0
        df_p['val'] = df_p.apply(procesar_saldo, axis=1)
        st_res = df_p.groupby(['equipo', 'marca', 'modelo']).agg({'val': 'sum'}).reset_index()
        st_res = st_res[st_res['val'] > 0]
    else:
        st_res = pd.DataFrame(columns=['equipo', 'marca', 'modelo', 'val'])

    # --- 2. BODEGA (Solo Equipos Operativos en Bodega) ---
    # REGLA: Destino Bodega + NO Periférico + NO Dañado
    bod_res = df_c[es_destino_bodega & ~es_periferico & ~es_dañado].copy()

    # --- 3. DAÑADOS (El Cementerio) ---
    # REGLA: Cualquier cosa con estado Dañado/Obsoleto
    danados_res = df_c[es_dañado].copy()

    return st_res, bod_res, danados_res, df_c
# ==========================================
# 5. PROMPT CEREBRO LAIA
# ==========================================
## ROLE: LAIA v2.0 – Auditora de Inventario Multitarea 
SYSTEM_PROMPT = """
# LAIA — Auditora de Bodega TI

## IDENTIDAD Y COMPORTAMIENTO
Eres LAIA, auditora experta de inventario TI y hardware. No eres un asistente conversacional; eres una función técnica especializada.
Tu único objetivo es registrar, validar y auditar equipos en la base de datos de inventario con criterio profesional de hardware.

Tienes conocimiento profundo de:
- Arquitectura de hardware (CPU, RAM, almacenamiento, placas, periféricos).
- Generaciones y rendimiento real de procesadores (Intel, AMD).
- Ciclo de vida de equipos TI, obsolescencia técnica y criterios de baja.
- Diagnóstico básico de estado físico y funcional de equipos.
- Flujos reales de bodega, stock, despacho, recepción y chatarrización.

Tono frío, directo y técnico. Sin cortesía innecesaria. Sin divagación.
Cada respuesta debe avanzar el registro.
Si el input no es inventario, responde de manera fria y amable y redirige al trabajo.
No hagas charla ni preguntas sociales.
Si el usuario se equivoca, corrige como hecho técnico, sin disculpas.

Si te preguntan quién eres, responde solo con tus funciones técnicas y redirige a una acción concreta.

## PIPELINE DE PROCESAMIENTO (OBLIGATORIO)

1) Detecta TODOS los equipos mencionados.
   No mezcles ítems distintos. Si hay duda, sepáralos.
   Determina el tipo de movimiento:
   - RECIBIDO: el equipo entra
   - ENVIADO: el equipo sale

2) Campos obligatorios:
   - origen (siempre)
   - destino (siempre)
   - tipo (siempre)
   - fecha_llegada (recibido)
   - marca (siempre)
   - marca (siempre)
   Campos condicionales:
   - fecha_llegada → solo si tipo = RECIBIDO
   - pasillo, estante, repisa → solo si destino = "Bodega"
   - procesador, ram, disco → solo si categoria = Cómputo

   Inferencias permitidas:
   - “enviamos” → origen = "Bodega"
   - “nos llegó / me llegó” → origen = proveedor o agencia mencionada
   - Si RECIBIDO sin fecha → usa fecha actual (YYYY-MM-DD)
   - Normaliza procesadores humanos (ej: “i5 de 8va”)

   Si falta un campo obligatorio no inferible → status = QUESTION
   Si todo está completo → status = READY

3) Clasificación técnica automática:
   - Core 2 Duo, Pentium, Celeron o ≤ 8va Gen → "Obsoleto / Pendiente Chatarrización"
   - 9na Gen → evalúa contexto
   - ≥ 10ma Gen → "Bueno" salvo evidencia contraria

   Si equipo ≥ 10ma Gen y disco HDD → añade reporte sugiriendo SSD.

   Si estado = "Dañado" u "Obsoleto / Pendiente Chatarrización":
   → destino FORZADO = "CHATARRA / BAJA" sin preguntar.

4) Reglas de origen y destino:
   - Ciudad o agencia mencionada → es el destino.
   - RECIBIDO → origen externo, destino interno.
   - ENVIADO → origen interno, destino externo.
   - Periférico RECIBIDO con usuario → destino = "STOCK".
   - Equipos de cómputo NUNCA van a "STOCK".

5) Override de usuario (PRIORIDAD ABSOLUTA):
   Si el usuario dice explícitamente “enviar así”, “no tengo más datos”, “rellena con N/A”:
   - Ignora bloqueos
   - Rellena faltantes con "N/A"
   - Marca status = READY

## FORMATO DE SALIDA

Devuelve SIEMPRE JSON.
Puedes escribir una breve frase técnica antes del JSON y también usar el campo "missing_info" dentro del JSON para detallar lo que falta.
No des detalles de lo que el usuario ingresa, solo datos faltantes segun item 2) "Campos obligatorios" y sugerencias.
{
  "status": "READY | QUESTION | IDLE",
  "missing_info": "",
  "items": [
    {
      "categoria_item": "Computo | Pantalla | Periferico | Consumible",
      "tipo": "Recibido | Enviado",
      "equipo": "",
      "marca": "",
      "modelo": "",
      "serie": "",
      "cantidad": 1,
      "estado": "Nuevo | Bueno | Obsoleto / Pendiente Chatarrización | Dañado",
      "procesador": "",
      "ram": "",
      "disco": "",
      "reporte": "",
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
    # A. Mostrar historial de mensajes
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # B. Entrada de usuario (Asegúrate de que este 'if' esté alineado con el 'for' de arriba)
    if prompt := st.chat_input("Dime qué llegó o qué enviaste..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            with st.spinner("LAIA auditando información..."):
                # 1. Preparar contexto y memoria
                lecciones, _ = obtener_github(FILE_LECCIONES)
                memoria_err = "\n".join([f"- {l['lo_que_hizo_mal']} -> {l['como_debe_hacerlo']}" for l in lecciones]) if lecciones else ""
                contexto_tabla = json.dumps(st.session_state.draft, ensure_ascii=False) if st.session_state.draft else "[]"

                mensajes_api = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "system", "content": f"LECCIONES TÉCNICAS:\n{memoria_err}"},
                    {"role": "system", "content": f"ESTADO ACTUAL: {contexto_tabla}"}
                ]

                # Añadir historial reciente para que LAIA no pierda el hilo
                for m in st.session_state.messages[-10:]:
                    mensajes_api.append(m)

                # 2. Llamada a OpenAI
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=mensajes_api,
                    temperature=0
                )

                raw_content = response.choices[0].message.content
                
                # 3. Procesar Voz y Datos usando la función extraer_json
                texto_fuera, res_txt = extraer_json(raw_content)
                
                try:
                    res_json = json.loads(res_txt) if res_txt else {}
                except:
                    res_json = {}

                # Unir el habla de LAIA (lo que dice fuera y dentro del JSON)
                voz_interna = res_json.get("missing_info", "")
                msg_laia = f"{texto_fuera}\n{voz_interna}".strip()
                if not msg_laia: msg_laia = "Instrucción técnica procesada."

                # Guardar y mostrar mensaje de LAIA
                st.session_state.messages.append({"role": "assistant", "content": msg_laia})
                with st.chat_message("assistant"):
                    st.markdown(msg_laia)

                # 4. Actualizar el borrador si hay ítems nuevos o cambios
                if "items" in res_json and res_json["items"]:
                    st.session_state.draft = res_json["items"]
                    st.session_state.status = res_json.get("status", "QUESTION")

                    if st.session_state.status == "READY":
                        st.success("✅ Datos auditados. Listo para guardar.")
                    
                    time.sleep(1)
                    st.rerun()

        except Exception as e:
            st.error(f"Error en el motor de LAIA: {str(e)}")

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
   
  if st.button("🔄 Sincronizar Datos de GitHub"):
    st.rerun()

  hist, _ = obtener_github(FILE_HISTORICO)
   
  if hist:
    df_h_raw = pd.DataFrame(hist)
     
    # --- AQUÍ ES EL CAMBIO: Recibimos 4 variables ahora ---
    st_res, bod_res, danados_res, df_h = calcular_stock_web(df_h_raw)
     
    # 4. Mostramos métricas
    k1, k2 = st.columns(2)
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
        st_res.to_excel(writer, index=False, sheet_name='Stock (Saldos)')
       
      # HOJA 3: BODEGA
      if not bod_res.empty:
        bod_res.to_excel(writer, index=False, sheet_name='BODEGA')

      # HOJA 4: DAÑADOS
      if not danados_res.empty:
        danados_res.to_excel(writer, index=False, sheet_name='DAÑADOS')
     
    st.download_button(
      label="📥 DESCARGAR EXCEL SINCRONIZADO (4 HOJAS)",
      data=buffer.getvalue(),
      file_name=f"Inventario_Jaher_{datetime.datetime.now().strftime('%d_%m_%H%M')}.xlsx",
      mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      type="primary" 
    )

    # 5. Mostrar la tabla en la web (el historial)
    st.write("### 📜 Últimos Movimientos en el Histórico")
    st.dataframe(df_h.tail(20), use_container_width=True) 
      
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
