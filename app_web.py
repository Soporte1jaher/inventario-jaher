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
    # 1. Intentamos obtener lo que ya hay
    actuales, sha = obtener_github(archivo)
    
    # --- CANDADO DE SEGURIDAD TOTAL ---
    # Si 'actuales' es None, es porque el archivo está corrupto o no se pudo leer.
    # PROHIBIMOS GUARDAR para no sobrescribir el desastre.
    if actuales is None:
        st.error(f"🛡️ SEGURIDAD ACTIVADA: No se puede guardar en {archivo} porque el archivo original está dañado. Repáralo en GitHub primero.")
        return False

    # 2. Mezclamos los datos
    if isinstance(datos, list):
        actuales.extend(datos)
    else:
        actuales.append(datos)

    # 3. Subimos a GitHub
    payload = {
        "message": mensaje,
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode()).decode()
    }
    
    if sha:
        payload["sha"] = sha
        
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}"
    
    resp = requests.put(url, headers=HEADERS, json=payload)
    
    if resp.status_code in [200, 201]:
        return True
    else:
        st.error(f"❌ Error al subir: {resp.text}")
        return False

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
## ROLE: LAIA v2.0 – Auditora de Inventario Multitarea 
SYSTEM_PROMPT = """
## ROLE: LAIA v7.0 – Auditora Senior de Inventario (Hardware & Logística)

Eres una auditora técnica experta. Tu prioridad es la PRECISIÓN y la MEMORIA.

### 1. REGLA DE ORO DE ACTUALIZACIÓN (VITAL):
- Recibirás un "BORRADOR ACTUAL" con lo que ya está en la tabla.
- Si el usuario aporta datos que faltan (serie, modelo, origen, guía) para un equipo que YA ESTÁ en la tabla, **ACTUALIZA LA FILA EXISTENTE**. 
- **NO crees filas duplicadas**. Si el usuario dice "la serie es X", busca el ítem que no tenía serie y pónsela.
- **PROHIBIDO BORRAR:** No elimines datos que ya estaban en el borrador (como la marca o el estado) solo porque el usuario no los repitió.

### 2. CRITERIOS TÉCNICOS AUTOMÁTICOS:
- **CPU < 10ma Gen (ej. i5-8xxx, i7-4xxx):** Estado = "Obsoleto / Pendiente Chatarrización".
- **CPU >= 10ma Gen:** Estado = "Bueno".
- **Hardware >= 10ma Gen + HDD:** Reporte = "CRÍTICO: Requiere cambio a SSD".
- **Categorías:** Monitor/TV -> "Pantalla", Laptop/PC/All-in-one -> "Computo".

### 3. REGLAS DE AUDITORÍA:
Para que status sea "READY", CADA fila de la tabla debe tener:
- **serie y modelo:** Obligatorio para Computo y Pantalla.
- **guia, origen y fecha_llegada:** Obligatorio para ingresos ("Recibido").

### 4. FORMATO DE SALIDA (ESTRICTAMENTE JSON):
Debes responder ÚNICAMENTE con este formato JSON:
{
 "status": "READY" o "QUESTION",
 "missing_info": "Especifca qué falta y en qué ítem",
 "items": [
  {
   "categoria_item": "Computo/Pantalla/Periferico",
   "tipo": "Recibido/Enviado",
   "equipo": "",
   "marca": "",
   "modelo": "",
   "serie": "",
   "cantidad": 1,
   "estado": "Bueno/Malo/Obsoleto/Chatarrización",
   "procesador": "",
   "ram": "",
   "disco": "",
   "reporte": "Diagnósticos técnicos automáticos aquí",
   "origen": "",
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

    # 2. Funciones de Auditoría Interna
    def auditar_items_local(items):
        faltantes = set()
        for i, it in enumerate(items):
            eq = str(it.get("equipo", "")).lower()
            tipo = str(it.get("tipo", "")).lower()
            if not it.get("equipo"): continue
            
            # Regla para Hardware Crítico
            if any(p in eq for p in ["monitor", "pantalla", "laptop", "pc", "cpu", "computador"]):
                if not it.get("serie"): faltantes.add(f"serie (ítem {i+1})")
                if not it.get("modelo"): faltantes.add(f"modelo (ítem {i+1})")
            
            # Regla para Logística
            if "recibido" in tipo or it.get("guia") or it.get("origen"):
                if not it.get("guia"): faltantes.add(f"guía (ítem {i+1})")
                if not it.get("origen"): faltantes.add(f"origen (ítem {i+1})")
                if not it.get("fecha_llegada"): faltantes.add(f"fecha (ítem {i+1})")
        return sorted(faltantes)

    # 3. Entrada de Chat
    if prompt := st.chat_input("Dime qué llegó o qué enviaste..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            with st.spinner("LAIA procesando..."):
                # Contexto de la tabla para que la IA no olvide nada
                contexto_tabla = json.dumps(st.session_state.draft, ensure_ascii=False) if st.session_state.draft else "[]"
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "system", "content": f"BORRADOR ACTUAL EN TABLA (NO PERDER DATOS): {}"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0
                )

                res_txt = extraer_json(response.choices[0].message.content)
                if not res_txt: raise Exception("LAIA no devolvió un formato válido.")
                
                res_json = json.loads(res_txt)
                
                # ACTUALIZACIÓN TOTAL: Reemplazamos el borrador con la versión procesada por la IA
                if "items" in res_json:
                    st.session_state.draft = res_json["items"]

                # Auditoría de control
                faltantes = auditar_items_local(st.session_state.draft)
                if faltantes:
                    st.session_state.status = "QUESTION"
                    st.session_state.missing_info = "Falta: " + ", ".join(faltantes)
                    msg_laia = f"⛔ {st.session_state.missing_info}"
                else:
                    st.session_state.status = "READY"
                    st.session_state.missing_info = ""
                    msg_laia = "✅ TABLA LISTA PARA ENVIAR"

                with st.chat_message("assistant"):
                    st.markdown(msg_laia)
                st.session_state.messages.append({"role": "assistant", "content": msg_laia})
                st.rerun()

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

    # 4. Tabla de Edición en Vivo
    if st.session_state.draft:
        st.divider()
        st.subheader("📊 Tabla de Inventario (Edición en Vivo)")
        
        df_editor = pd.DataFrame(st.session_state.draft)
        cols_orden = ["equipo", "marca", "modelo", "serie", "cantidad", "estado", "tipo", "origen", "guia", "fecha_llegada", "ram", "procesador", "disco", "reporte"]
        df_editor = df_editor.reindex(columns=cols_orden).fillna("")

        edited_df = st.data_editor(df_editor, num_rows="dynamic", use_container_width=True, key="main_editor")
        
        # Sincronizar edición manual con el estado
        if not df_editor.equals(edited_df):
            st.session_state.draft = edited_df.to_dict("records")
            # Re-auditar tras cambio manual
            f_manual = auditar_items_local(st.session_state.draft)
            st.session_state.status = "QUESTION" if f_manual else "READY"
            st.session_state.missing_info = ("Falta: " + ", ".join(f_manual)) if f_manual else ""

        # 5. Botones de Acción
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("🚀 ENVIAR AL BUZÓN", type="primary"):
                if st.session_state.status == "QUESTION":
                    st.error(f"Bloqueado: {st.session_state.missing_info}")
                else:
                    with st.spinner("Guardando..."):
                        fecha_now = (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                        for d in st.session_state.draft: d["fecha_registro"] = fecha_now
                        
                        if enviar_github(FILE_BUZON, st.session_state.draft):
                            st.success("Sincronizado!")
                            st.session_state.draft = []
                            st.session_state.messages = []
                            time.sleep(1)
                            st.rerun()
        with c2:
            if st.button("🗑️ Cancelar"):
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
            df_h.to_excel(writer, index=False, sheet_name='Historico_Real')
            if not st_res.empty:
                st_res.to_excel(writer, index=False, sheet_name='Resumen_Stock')
        
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
