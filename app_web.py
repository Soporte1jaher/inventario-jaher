import streamlit as st
import pandas as pd
import json

from ai_logic import client, SYSTEM_PROMPT, extraer_json
from github_utils import obtener_github, enviar_github
from inventory_engine import calcular_stock_web


# -------------------------------------------------
# CONFIGURACIÓN GLOBAL
# -------------------------------------------------
st.set_page_config(page_title="LAIA", layout="wide")
st.title("🧠 LAIA — Auditora TI")

FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"

if "messages" not in st.session_state:
    st.session_state.messages = []

if "draft" not in st.session_state:
    st.session_state.draft = []

if "status" not in st.session_state:
    st.session_state.status = "NEW"

if "missing_info" not in st.session_state:
    st.session_state.missing_info = ""


# -------------------------------------------------
# TABS
# -------------------------------------------------
t1, t2, t3 = st.tabs(["💬 Chat Auditor", "📊 Stock Real", "🗑️ Limpieza"])

# =================================================
# TAB 1 — CHAT
# =================================================
with t1:
    # A. Mostrar historial de mensajes
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # B. Entrada de usuario
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
                    {"role": "system", "content": f"ESTADO ACTUAL: {contexto_tabla}"}
                ]

                for m in st.session_state.messages[-10:]:
                    mensajes_api.append(m)

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=mensajes_api,
                    temperature=0
                )

                raw_content = response.choices[0].message.content
                texto_fuera, res_txt = extraer_json(raw_content)
                try:
                    res_json = json.loads(res_txt) if res_txt else {}
                except:
                    res_json = {}

                voz_interna = res_json.get("missing_info", "")
                msg_laia = f"{texto_fuera}\n{voz_interna}".strip()
                if not msg_laia: msg_laia = "Instrucción técnica procesada."

                st.session_state.messages.append({"role": "assistant", "content": msg_laia})
                with st.chat_message("assistant"):
                    st.markdown(msg_laia)

                if "items" in res_json and res_json["items"]:
                    nuevos_items = res_json["items"]
            
            # Si el borrador está vacío, simplemente lo llenamos
                    if not st.session_state.draft:
                      st.session_state.draft = nuevos_items
                else:
                # LÓGICA DE FUSIÓN: 
                # Creamos un diccionario usando la 'serie' como clave para actualizar
                # Si el item no tiene serie, lo agregamos como nuevo
                        dict_actual = { (i.get('serie') or i.get('modelo') or i.get('equipo')): i for i in st.session_state.draft }
                
                        for item in nuevos_items:
                         key = item.get('serie') or item.get('modelo') or item.get('equipo')
                         dict_actual[key] = item # Esto actualiza si existe o agrega si es nuevo
                
                         st.session_state.draft = list(dict_actual.values())
        
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
        
        # 🔒 AUTOCORRECCIÓN EN TIEMPO REAL (ANTES DE CREAR df_editor)
        for d in st.session_state.draft:
            proc = d.get("procesador", "")
            gen = extraer_gen(proc)
            if gen == "obsoleto":
                d["estado"] = "Obsoleto / Pendiente Chatarrización"
                d["destino"] = "CHATARRA / BAJA"
                d["origen"] = d.get("origen", "Bodega")

        df_editor = pd.DataFrame(st.session_state.draft)
        cols_base = ["categoria_item", "equipo", "marca", "modelo", "serie", "cantidad", "estado", "tipo", "origen", "destino",
                     "pasillo", "estante", "repisa", "guia", "fecha_llegada", "ram", "disco", "procesador", "reporte"]
        for c in cols_base:
            if c not in df_editor.columns: df_editor[c] = ""
        
        df_editor = df_editor.reindex(columns=cols_base).fillna("N/A")
        edited_df = st.data_editor(df_editor, num_rows="dynamic", use_container_width=True, key="editor_v11")

        if not df_editor.equals(edited_df):
            st.session_state.draft = edited_df.to_dict("records")

        # --- GLPI ---
        col_glpi1, col_glpi2 = st.columns([2, 1])
        with col_glpi1:
            if st.button("🔍 SOLICITAR BÚSQUEDA EN OFICINA"):
                serie_valida = next((item.get('serie') for item in st.session_state.draft if item.get('serie') and item.get('serie') != "N/A"), None)
                if serie_valida:
                    if solicitar_busqueda_glpi(serie_valida):
                        st.toast(f"Pedido enviado para serie {serie_valida}", icon="📡")
                        time.sleep(10)
                        st.rerun()
                else:
                    st.warning("⚠️ No hay una serie válida para buscar.")
        
        with col_glpi2:
            if st.button("🔄 REVISAR Y AUTORELLENAR"):
                res_glpi = revisar_respuesta_glpi()
                if res_glpi and res_glpi.get("estado") == "completado":
                    specs_oficina = res_glpi.get("specs", {})
                    serie_buscada = res_glpi.get("serie")
                    encontrado = False
                    nuevo_borrador = []
                    for item in st.session_state.draft:
                        if item.get("serie") == serie_buscada:
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
                        st.rerun()
                else:
                    st.info("⏳ Esperando que la PC de la oficina envíe la ficha técnica...")

        # 4. Botones de acción
    c1, c2 = st.columns([1, 4]) # Aquí creamos c1 y c2

    with c1:
        # 1. Creamos la casilla para forzar el guardado
        forzar = st.checkbox("🔓 Forzar")

    with c2:
        # 2. El botón se activa si la IA dice READY o si marcas "Forzar"
        if st.session_state.status == "READY" or forzar:
            if st.button("🚀 GUARDAR EN HISTÓRICO", type="primary", use_container_width=True):
                
                # --- Lógica de chatarrización ---
                for d in st.session_state.draft:
                    proc = d.get("procesador", "")
                    if extraer_gen(proc) == "obsoleto":
                        d["estado"] = "Obsoleto / Pendiente Chatarrización"
                        d["destino"] = "CHATARRA / BAJA"
                        d["origen"] = d.get("origen", "Bodega")

                # --- Sellar con fecha ---
                ahora = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                for d in st.session_state.draft: 
                    d["fecha_registro"] = ahora
                
                # --- Guardar ---
                if enviar_github(FILE_BUZON, st.session_state.draft, "Registro LAIA"):
                    st.success("✅ ¡Guardado con éxito!")
                    st.session_state.draft = []
                    st.session_state.messages = []
                    st.session_state.status = "NEW"
                    time.sleep(1)
                    st.rerun()
        else:
            # Botón bloqueado si no hay nada
            st.button("🚀 GUARDAR (BLOQUEADO)", disabled=True, use_container_width=True)

    # Botón de descartar (puedes ponerlo abajo o en otra columna)
    if st.button("🗑️ Descartar Todo"):
        st.session_state.draft = []
        st.session_state.messages = []
        st.session_state.status = "NEW"
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
  st.subheader("🗑️ Limpieza Inteligente del Historial")
  st.markdown("""
  Usa este panel para eliminar registros específicos mediante lenguaje natural. 
  LAIA analizará el historial para encontrar coincidencias.
  """)
  st.info("💡 Ejemplos: 'Borra lo de Latacunga', 'Elimina la serie 89238928', 'Limpia los teclados de marca N/A'")

  txt_borrar = st.text_input("¿Qué deseas eliminar?", placeholder="Escribe tu instrucción aquí...")

  if st.button("🔥 BUSCAR Y GENERAR ORDEN DE BORRADO", type="secondary"):
    if txt_borrar:
      try:
        with st.spinner("LAIA analizando historial para identificar el objetivo..."):
          # 1. Obtener contexto real del historial
          hist, _ = obtener_github(FILE_HISTORICO)
          # Mandamos los últimos 40 registros para que la IA vea nombres reales
          contexto_breve = json.dumps(hist[-40:], ensure_ascii=False) if hist else "[]"

          p_db = f"""
          Actúa como DBA Senior. Tu objetivo es generar un comando de borrado en JSON.
          Analiza el HISTORIAL ACTUAL para encontrar qué columna y valor coinciden con la instrucción.

          COLUMNAS VÁLIDAS: 'equipo', 'marca', 'modelo', 'serie', 'guia', 'destino', 'origen', 'categoria_item'.

          HISTORIAL ACTUAL (Muestra): {contexto_breve}

          INSTRUCCIÓN DEL USUARIO: "{txt_borrar}"

          REGLAS DE SALIDA:
          1. Si pide borrar todo: {{"accion": "borrar_todo"}}
          2. Si es específico:
             - Identifica la columna que mejor encaja.
             - Si el usuario menciona un lugar, suele ser 'destino' u 'origen'.
             - Si menciona un código largo, es 'serie' o 'guia'.
             - Genera: {{"accion": "borrar_filtro", "columna": "nombre_de_columna", "valor": "valor_exacto_encontrado_en_historial"}}

          RESPONDE ÚNICAMENTE EL JSON.
          """

          response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": p_db}],
            temperature=0
          )

          raw_res = response.choices[0].message.content.strip()
          # Extraer JSON por si la IA pone texto extra
          inicio = raw_res.find("{")
          fin = raw_res.rfind("}") + 1
          order = json.loads(raw_res[inicio:fin])

          # 2. Enviar la orden al buzón para que el Robot de la PC la ejecute
          if enviar_github(FILE_BUZON, order, "Orden de Borrado Inteligente"):
            st.success("✅ Orden de borrado enviada con éxito.")
            st.json(order)
            st.warning("⚠️ El Robot en tu PC procesará esto en unos segundos y actualizará el Excel y la Nube.")
          else:
            st.error("❌ No se pudo enviar la orden a GitHub.")

      except Exception as e:
        st.error(f"Error en el motor de limpieza: {e}")
    else:
      st.warning("Escribe una instrucción antes de presionar el botón.")
