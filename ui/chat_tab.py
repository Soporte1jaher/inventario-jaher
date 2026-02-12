import streamlit as st
import pandas as pd
import time
import datetime
from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler
from modules.stock_calculator import StockCalculator

class ChatTab:
    """Tab de chat para auditoría - CORREGIDO"""
    
    def __init__(self): # <--- CORREGIDO: Tenía que ser __init__
        self.ai_engine = AIEngine()
        self.github = GitHubHandler()
        self.stock_calc = StockCalculator()
        
        # Inicializar estado de sesión
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "draft" not in st.session_state:
            st.session_state.draft = []
        if "status" not in st.session_state:
            st.session_state.status = "NEW"
        if "missing_info" not in st.session_state:
            st.session_state.missing_info = ""

    def render(self):
        # A. Mostrar historial de mensajes
        for m in st.session_state.messages:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
        
        # B. Entrada de usuario
        if prompt := st.chat_input("Dime qué llegó o qué enviaste..."):
            self._procesar_mensaje(prompt)
        
        # C. Tabla de borrador y botones
        if st.session_state.draft:
            self._mostrar_borrador()

    def _procesar_mensaje(self, prompt):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        try:
            with st.spinner("LAIA auditando información..."):
                lecciones = self.github.obtener_lecciones()
                
                resultado = self.ai_engine.procesar_input(
                    user_input=prompt,
                    lecciones=lecciones,
                    borrador_actual=st.session_state.draft,
                    historial_mensajes=st.session_state.messages
                )
                
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": resultado["mensaje"]
                })
                
                with st.chat_message("assistant"):
                    st.markdown(resultado["mensaje"])
                
                res_json = resultado["json_response"]
                if "items" in res_json and res_json["items"]:
                    self._actualizar_borrador(res_json["items"])
                
                st.session_state.status = res_json.get("status", "QUESTION")
                if st.session_state.status == "READY":
                    st.success("✅ Datos auditados. Listo para guardar.")
        except Exception as e:
            st.error(f"Error en el motor de LAIA: {str(e)}")

    def _actualizar_borrador(self, nuevos_items):
        if not st.session_state.draft:
            st.session_state.draft = nuevos_items
        else:
            dict_actual = {(i.get('serie') or i.get('modelo') or i.get('equipo')): i for i in st.session_state.draft}
            for item in nuevos_items:
                key = item.get('serie') or item.get('modelo') or item.get('equipo')
                dict_actual[key] = item
            st.session_state.draft = list(dict_actual.values())

    def _mostrar_borrador(self):
        st.divider()
        st.subheader("📊 Borrador de Movimientos")
        
        # Sincronizar con el calculador de stock modular
        st.session_state.draft = self.stock_calc.aplicar_reglas_obsolescencia(st.session_state.draft)
        
        df_editor = pd.DataFrame(st.session_state.draft)
        cols_base = ["categoria_item", "equipo", "marca", "modelo", "serie", "cantidad", "estado", "tipo", "origen", "destino", "pasillo", "estante", "repisa", "guia", "fecha_llegada", "ram", "disco", "procesador", "reporte"]
        
        for c in cols_base:
            if c not in df_editor.columns: df_editor[c] = ""
        
        df_editor = df_editor.reindex(columns=cols_base).fillna("N/A")
        edited_df = st.data_editor(df_editor, num_rows="dynamic", use_container_width=True, key="editor_v12")
        
        if not df_editor.equals(edited_df):
            st.session_state.draft = edited_df.to_dict("records")
        
        self._mostrar_botones_accion()

    def _mostrar_botones_accion(self):
        c1, c2 = st.columns([1, 4])
        with c1:
            forzar = st.checkbox("🔓 Forzar")
        with c2:
            if st.session_state.status == "READY" or forzar:
                if st.button("🚀 GUARDAR Y ENVIAR AL ROBOT", type="primary", use_container_width=True):
                    self._guardar_borrador()
            else:
                st.button("🚀 GUARDAR (BLOQUEADO)", disabled=True, use_container_width=True)
        
        if st.button("🗑️ Descartar Todo"):
            self._limpiar_sesion()

    def _guardar_borrador(self):
        # Sellar con fecha
        ahora = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
        for item in st.session_state.draft:
            item["fecha_registro"] = ahora
        
        # 🔥 EL CAMBIO CLAVE: Se envía al BUZÓN para que el Robot lo vea
        if self.github.enviar_a_buzon(st.session_state.draft):
            st.success("✅ ¡Enviado al Robot de la PC!")
            self._limpiar_sesion()
            time.sleep(1)
            st.rerun()

    def _limpiar_sesion(self):
        st.session_state.draft = []
        st.session_state.messages = []
        st.session_state.status = "NEW"
        st.rerun()
