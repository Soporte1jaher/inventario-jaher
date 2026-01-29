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
    # Asegúrate de que esta línea esté indentada exactamente con 4 espacios
    timestamp = int(time.time())
    url = f"https://api.github.com/repos/{}/{}/contents/{}?t={timestamp}"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            d = resp.json()
            contenido_decodificado = base64.b64decode(d['content']).decode('utf-8')
            return json.loads(contenido_decodificado), d['sha']
    except Exception as e:
        st.error(f"Error al obtener datos de GitHub: {e}")
    return [], None

def enviar_github(archivo, datos, mensaje="LAIA Update"):
    # 1. Intentamos obtener lo que ya hay
    actuales, sha = obtener_github(archivo)
    
    # --- CANDADO DE SEGURIDAD ---
    # Si 'actuales' es una lista vacía pero el archivo es el histórico,
    # significa que algo falló en la descarga. ¡NO sobreescribimos!
    if sha is None:
        st.error(f"❌ Error crítico: No se pudo obtener el SHA de {archivo}. Abortando para evitar pérdida de datos.")
        return False

    # 2. Mezclamos los datos
    if isinstance(datos, list):
        actuales.extend(datos)
    else:
        actuales.append(datos)

    # 3. Subimos a GitHub
    payload = {
        "message": mensaje,
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode()).decode(),
        "sha": sha
    }
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_PATH}"
    resp = requests.put(url, headers=HEADERS, json=payload)
    
    if resp.status_code in [200, 201]:
        return True
    else:
        st.error(f"❌ Error al subir: {resp.text}")
        return False
    
def aprender_leccion(error, correccion):
    lecciones, sha = obtener_github(FILE_LECCIONES)
    nueva = {
        "fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "lo_que_hizo_mal": error,
        "como_debe_hacerlo": correccion
    }
    lecciones.append(nueva)
    # Guardamos solo las últimas 15 para que no se sature el cerebro
    if enviar_github(FILE_LECCIONES, lecciones[-15:], "LAIA: Nueva lección aprendida"):
        return True
    return False
# ==========================================
# 4. MOTOR DE STOCK
# ==========================================
def calcular_stock_web(df):
    if df.empty: return pd.DataFrame(), pd.DataFrame()
    df_c = df.copy()
    df_c.columns = df_c.columns.str.lower().str.strip()
    for col in ['estado', 'estado_fisico', 'tipo', 'destino', 'equipo', 'marca', 'cantidad', 'modelo']:
        if col not in df_c.columns: df_c[col] = "No especificado"
    df_c['cant_n'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(1)

    def procesar_fila(row):
        est = str(row['estado']).lower()
        t = str(row['tipo']).lower()
        d = str(row['destino']).lower()
        eq = str(row['equipo']).lower()
        cant = row['cant_n']
        perifericos = ['mouse', 'teclado', 'cable', 'hdmi', 'ponchadora', 'cargador']
        if any(p in eq for p in perifericos):
            return cant if 'recibido' in t else -cant
        if 'dañ' in est or 'obs' in est: return 0
        if d == 'stock' or 'recibido' in t: return cant
        if 'enviado' in t: return -cant
        return 0

    df_c['val'] = df_c.apply(procesar_fila, axis=1)
    resumen = df_c.groupby(['equipo', 'marca', 'modelo', 'estado_fisico'])['val'].sum().reset_index()
    movimientos = df_c[df_c['val'] != 0]
    return resumen[resumen['val'] > 0], movimientos

# ==========================================
# 5. PROMPT CEREBRO LAIA
# ==========================================
SYSTEM_PROMPT = """
Eres LAIA (Logic & Audit Inventory Assistant), la Auditora Senior de Inventarios de Jaher. Tu inteligencia es superior, deductiva y meticulosa. No eres una secretaria; eres una auditora con capacidad de RAZONAMIENTO y TOMA DE DECISIONES.

=== CAPA 0: RAZONAMIENTO Y OBEDIENCIA AL USUARIO (CRÍTICO) ===
1. EL USUARIO ES JEFE: Si el usuario dice "Déjame enviar", "Ya no quiero agregar datos", "Nada más", "Ponle N/A a todo" o "Envía así", tu obligación es RAZONAR que la auditoría manual ha terminado. 
   - ACCIÓN: Llena TODOS los campos vacíos con "N/A" inmediatamente y cambia el status a "READY".
2. MAPEO INTELIGENTE DE FECHAS: Si el usuario menciona una fecha (ej: 29 de enero), búscala y pégala en la columna 'fecha_llegada' de los equipos tipo 'Recibido'. No vuelvas a preguntar por ella.
3. MAPEO DE INTENCIONES: Si el usuario dice "Pon fecha", "Pon guía" o "Añade X", hazlo en la tabla antes de generar el mensaje de faltantes.

=== CAPA 1: REGLAS DE PERSISTENCIA Y MEMORIA ===
4. PROHIBIDO BORRAR: Tu JSON debe incluir SIEMPRE los ítems que ya estaban en el 'BORRADOR ACTUAL'. Solo añade los nuevos o actualiza los existentes.
5. MAPEO POR CIUDAD: Si el usuario dice "La de Latacunga es...", actualiza SOLO esa fila buscando el destino 'Latacunga'.

=== CAPA 2: REGLAS DE ORO DE AUDITORÍA JAHER ===
6. DESGLOSE OBLIGATORIO: Laptop, CPU, Monitor, Impresora, Teclado y Mouse van en CELDAS SEPARADAS.
7. GUÍA HEREDADA: Si una Guía es para un equipo, aplícala automáticamente a todos los periféricos que lo acompañen.
8. BLOQUEO DE FECHA EN ENVIADOS: Tipo 'Enviado' -> fecha_llegada = "N/A". Prohibido pedirla.
9. OBLIGACIÓN EN RECIBIDOS: Tipo 'Recibido' -> fecha_llegada es OBLIGATORIA (a menos que el usuario use el Comando de Escape de la Regla 1).
10. HARDWARE GEN 10: 
AQUI QUIERO QUE RAZONES Y TE DES CUENTA DE LO SIGUIENTE:
    - Procesador <= Gen 9 -> Estado: 'Dañado', Destino: 'DAÑADOS'.
    - Procesador >= Gen 10 + HDD -> Estado: 'Dañado', Reporte: 'REQUIERE CAMBIO A SSD'.
    - Procesador >= Gen 10 + SSD -> Estado: 'Bueno'.
11. ESCRITURA LITERAL: Escribe la generación completa (ej: "Core i3 10ma Gen").

=== CAPA 3: PROTOCOLO DE RESPUESTA (CERO PING-PONG) ===
12. ANALISIS TÉCNICO: En 'missing_info', en lugar de solo pedir, sugiere: "He notado que faltan guías. Si no las tienes, dime 'así no más' para llenar con N/A y habilitar el envío".
13. STATUS READY: Solo se activa cuando todo está lleno o cuando el usuario da la orden de finalizar (Regla 1).

=== MATRIZ DE MAPEO TÉCNICO ===
- "240 SSD" -> 240GB SSD | "8 RAM" -> 8GB.
- "no llegaron con guia" -> guia: "N/A".
- "sin tornillos en la base" -> reporte: "Sin tornillos en la base".


SALIDA JSON (CONTRATO DE DATOS OBLIGATORIO):
{
 "status": "READY" o "QUESTION",
 "missing_info": "Mensaje amable pidiendo los datos faltantes",
 "items": [
  {
   "equipo": "...", 
   "marca": "...", 
   "modelo": "...", 
   "serie": "...", 
   "cantidad": 1,
   "estado": "Bueno/Dañado/Obsoleto", 
   "estado_fisico": "Nuevo/Usado",
   "tipo": "Recibido/Enviado", 
   "origen": "...", 
   "destino": "...", 
   "guia": "...",
   "reporte": "...",
   "disco": "...",
   "ram": "...",
   "procesador": "...",
   "fecha_llegada": "...",
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
    # 1. Mostrar historial
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): 
            st.markdown(m["content"])

    # 2. Entrada de chat
    if prompt := st.chat_input("Dime qué llegó o qué enviaste..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): 
            st.markdown(prompt)

        try:
            with st.spinner("LAIA Auditando y consultando su memoria..."):
                # --- LÓGICA DE APRENDIZAJE ---
                lecciones_previas, _ = obtener_github(FILE_LECCIONES)
                texto_memoria = "\n".join([f"- ERROR: {l['lo_que_hizo_mal']} | LECCIÓN: {l['como_debe_hacerlo']}" for l in lecciones_previas])
                
                # Inyectamos el aprendizaje en el cerebro de LAIA
                prompt_con_memoria = f"{SYSTEM_PROMPT}\n\n=== MEMORIA DE ERRORES PASADOS (PROHIBIDO REPETIR) ===\n{texto_memoria}"
                
                # Memoria de la tabla actual
                contexto_tabla = json.dumps(st.session_state.draft) if st.session_state.draft else "[]"
                
                # Llamada a la IA
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": prompt_con_memoria},
                        {"role": "user", "content": f"BORRADOR ACTUAL: {contexto_tabla}\n\nMENSAJE USUARIO: {prompt}"}
                    ],
                    temperature=0
                )
                
                # Procesar respuesta (Aquí estaba el error de alineación)
                res_txt = extraer_json(response.choices[0].message.content)
                if res_txt:
                    res_json = json.loads(res_txt)
                    st.session_state.draft = res_json.get("items", [])
                    st.session_state.status = res_json.get("status", "READY")
                    st.session_state.missing_info = res_json.get("missing_info", "")

                    msg_laia = f"✅ Tabla actualizada. {st.session_state.missing_info}" if st.session_state.status=="QUESTION" else "✅ Tabla lista para enviar."
                    with st.chat_message("assistant"): 
                        st.markdown(msg_laia)
                    st.session_state.messages.append({"role": "assistant", "content": msg_laia})
                    st.rerun()

        except Exception as e:
            st.error(f"❌ Error de Auditoría: {error_msg}")

    # 3. Tabla en Vivo y Botones
    if st.session_state.draft:
        st.divider()
        st.subheader("📊 Tabla de Inventario (Edición en Vivo)")
        
        df_editor = pd.DataFrame(st.session_state.draft)
        # Forzamos el orden de las columnas para que no se desordenen
        cols_orden = ["equipo","marca","modelo","serie","cantidad","estado","tipo","origen","destino","guia","fecha_llegada","ram","procesador","disco","reporte"]
        df_editor = df_editor.reindex(columns=cols_orden).fillna("")
        
        edited_df = st.data_editor(df_editor, num_rows="dynamic", use_container_width=True, key="auditoria_editor")
        
        if not df_editor.equals(edited_df):
            st.session_state.draft = edited_df.to_dict("records")

        c1, c2 = st.columns([1,4])
        with c1:
            if st.button("🚀 ENVIAR AL BUZÓN", type="primary"):
                if st.session_state.status == "QUESTION":
                    st.error(f"⛔ BLOQUEADO: {st.session_state.missing_info}")
                else:
                    with st.spinner("Sincronizando..."):
                        final_data = st.session_state.draft
                        fecha_now = (datetime.datetime.now(timezone.utc)-timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                        for d in final_data: d["fecha_registro"] = fecha_now
                        
                        if enviar_github(FILE_BUZON, final_data):
                            st.success("✅ Enviado con éxito!")
                            st.session_state.draft = []
                            st.session_state.messages = []
                            time.sleep(1)
                            st.rerun()
        with c2:
            if st.button("🗑️ Cancelar Todo"):
                st.session_state.draft = []
                st.session_state.messages = []
                st.rerun()
# --- Pestañas Stock y Limpieza quedan igual, integrando el cálculo de stock y generación de Excel del segundo código ---
with t2:
    hist, _ = obtener_github(FILE_HISTORICO)
    if hist:
        df_h = pd.DataFrame(hist)
        df_h.columns = df_h.columns.str.lower().str.strip()
        st_res, st_det = calcular_stock_web(df_h)

        k1, k2 = st.columns(2)
        k1.metric("📦 Stock Total", int(st_res['val'].sum()) if not st_res.empty else 0)
        k2.metric("🚚 Movimientos", len(df_h))

        if not st_res.empty:
            st.dataframe(
                st_res.pivot_table(
                    index=['equipo', 'marca'],
                    columns='estado_fisico',
                    values='val',
                    aggfunc='sum'
                ).fillna(0)
            )

        st.dataframe(st_det, use_container_width=True)
    else:
        st.info("Sincronizando con GitHub...")
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
