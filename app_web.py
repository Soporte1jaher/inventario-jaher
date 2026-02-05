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
    # Limpieza profunda de columnas
    df_c.columns = df_c.columns.str.lower().str.strip()
    
    # Asegurar que existan las columnas básicas
    for col in ['estado', 'tipo', 'equipo', 'cantidad']:
        if col not in df_c.columns: df_c[col] = ""
    
    # Convertir cantidad a número de forma segura
    df_c['cant_n'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(0)

    def procesar_fila(row):
        eq = str(row['equipo']).lower().strip()
        tipo = str(row['tipo']).lower().strip()
        est = str(row['estado']).lower().strip()
        cant = row['cant_n']

        # 1. Definir si es Entrada o Salida
        es_entrada = any(x in tipo for x in ['recibido', 'ingreso', 'entrada', 'llegó'])
        es_salida = any(x in tipo for x in ['enviado', 'salida', 'despacho', 'egreso', 'envié'])

        # 2. Lógica para Periféricos y Consumibles (Suma y Resta simple)
        perifericos = ['mouse', 'teclado', 'cable', 'hdmi', 'limpiador', 'cargador', 'toner', 'tinta']
        if any(p in eq for p in perifericos):
            if es_entrada: return cant
            if es_salida: return -cant
            return 0 # Si no se sabe qué es, no suma ni resta

        # 3. Lógica para Equipos Críticos (Solo suma si están en buen estado)
        if 'dañ' in est or 'obs' in est or 'chatarra' in est:
            return 0
        
        if es_entrada: return cant
        if es_salida: return -cant
        
        return 0

    df_c['val'] = df_c.apply(procesar_fila, axis=1)
    
    # Agrupamos para el resumen de saldos
    resumen = df_c.groupby(['equipo', 'marca', 'modelo']).agg({'val': 'sum'}).reset_index()
    resumen.columns = ['equipo', 'marca', 'modelo', 'variacion']
    
    # Solo mostramos en el stock lo que tiene saldo positivo
    stock_real = resumen[resumen['variacion'] > 0].copy()
    
    return stock_real, df_c

# ==========================================
# 5. PROMPT CEREBRO LAIA
# ==========================================
## ROLE: LAIA v2.0 – Auditora de Inventario Multitarea 
SYSTEM_PROMPT = """
## ROLE: LAIA v8.0 – Auditora Senior con Criterio Técnico

Eres una experta en hardware y gestión de activos. No eres un robot de entrada de datos, eres una analista.

### 1. TU RAZONAMIENTO TÉCNICO:
- Usa tu conocimiento sobre generaciones de procesadores, tipos de disco y memoria para evaluar el estado de los equipos. 
- Si detectas hardware antiguo (ej. procesadores de hace más de 10 años), clasifícalo como "Obsoleto / Pendiente Chatarrización" por iniciativa propia.
- Si ves una configuración desequilibrada (ej. un i7 moderno con disco mecánico), añade en 'reporte' tu recomendación técnica (ej. "Cambio a SSD sugerido").
- Aprende de la 'MEMORIA DE ERRORES' que se te proporcione para no repetir fallos previos.

### 2. GESTIÓN DE DATOS Y MEMORIA:
- **Actualización:** Si el usuario aporta datos de un equipo que ya está en el 'BORRADOR ACTUAL', actualiza esa fila. No la dupliques.
- **Flexibilidad:** Si el usuario no proporciona todos los datos (como serie o guía), pídeselos en una sola oración amable. 
- **Entrega:** Si el usuario decide no dar más datos, procesa el JSON con lo que tengas. Tu prioridad es que la tabla siempre esté lo más completa posible.

### 3. FORMATO DE SALIDA (ESTRICTAMENTE JSON):
{
 "status": "READY" (si es aceptable para inventario) o "QUESTION" (si falta algo crítico),
 "missing_info": "Tu mensaje corto pidiendo lo que falta",
 "items": [
  {
   "categoria_item": "Computo/Pantalla/Periferico",
   "tipo": "Recibido/Enviado",
   "equipo": "", "marca": "", "modelo": "", "serie": "",
   "cantidad": 1, "estado": "", "procesador": "", "ram": "", "disco": "",
   "reporte": "Tu análisis técnico aquí",
   "origen": "", "guia": "", "fecha_llegada": ""
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
    # 1. Historial
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # 2. Entrada de Chat
    if prompt := st.chat_input("Dime qué llegó o qué enviaste..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            with st.spinner("LAIA razonando..."):
                # Cargamos lecciones de errores pasados para que aprenda
                lecciones, _ = obtener_github(FILE_LECCIONES)
                memoria = "\n".join([f"- {l['lo_que_hizo_mal']} -> {l['como_debe_hacerlo']}" for l in lecciones]) if lecciones else ""
                
                contexto_tabla = json.dumps(st.session_state.draft, ensure_ascii=False) if st.session_state.draft else "[]"
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "system", "content": f"MEMORIA DE APRENDIZAJE:\n{memoria}"},
                        {"role": "system", "content": f"BORRADOR ACTUAL:\n{contexto_tabla}"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0
                )

                res_txt = extraer_json(response.choices[0].message.content)
                res_json = json.loads(res_txt)
                
                # Actualizar el borrador
                st.session_state.draft = res_json.get("items", [])
                st.session_state.status = res_json.get("status", "READY")
                st.session_state.missing_info = res_json.get("missing_info", "")

                msg_laia = f"🤖 {st.session_state.missing_info}" if st.session_state.missing_info else "✅ Entendido. Todo registrado."
                with st.chat_message("assistant"):
                    st.markdown(msg_laia)
                st.session_state.messages.append({"role": "assistant", "content": msg_laia})
                st.rerun()

        except Exception as e:
            st.error(f"Ocurrió un error: {e}")

    # 3. Tabla de Edición
    if st.session_state.draft:
        st.divider()
        df_editor = pd.DataFrame(st.session_state.draft)
        # Aseguramos que todas las columnas existan
        for c in ["equipo","marca","modelo","serie","cantidad","estado","tipo","origen","guia","fecha_llegada","reporte"]:
            if c not in df_editor.columns: df_editor[c] = ""
        
        edited_df = st.data_editor(df_editor, num_rows="dynamic", use_container_width=True)
        
        if not df_editor.equals(edited_df):
            st.session_state.draft = edited_df.to_dict("records")

        # 4. Botones
        c1, c2 = st.columns([1, 4])
        with c1:
            # Ahora el botón se habilita más fácil, confiando en el criterio de la IA
            if st.button("🚀 ENVIAR A GITHUB", type="primary"):
                fecha_now = (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                for d in st.session_state.draft: d["fecha_registro"] = fecha_now
                if enviar_github(FILE_BUZON, st.session_state.draft):
                    st.success("¡Datos guardados!")
                    st.session_state.draft = []
                    st.session_state.messages = []
                    st.rerun()
        with c2:
            if st.button("🗑️ Limpiar Borrador"):
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
