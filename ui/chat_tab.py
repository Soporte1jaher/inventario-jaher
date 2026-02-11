import streamlit as st
import pandas as pd
import time
import datetime
from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler
from modules.stock_calculator import StockCalculator

class ChatTab:
    """Tab de chat para auditoría"""
    
    def __init__(self):
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
        """Renderiza el tab completo"""
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
        """Procesa el mensaje del usuario"""
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        try:
            with st.spinner("LAIA auditando información..."):
                # Obtener lecciones
                lecciones = self.github.obtener_lecciones()
                
                # Procesar con IA
                resultado = self.ai_engine.procesar_input(
                    user_input=prompt,
                    lecciones=lecciones,
                    borrador_actual=st.session_state.draft,
                    historial_mensajes=st.session_state.messages
                )
                
                # Mostrar respuesta
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": resultado["mensaje"]
                })
                
                with st.chat_message("assistant"):
                    st.markdown(resultado["mensaje"])
                
                # Actualizar borrador
                res_json = resultado["json_response"]
                
                if "items" in res_json and res_json["items"]:
                    self._actualizar_borrador(res_json["items"])
                
                st.session_state.status = res_json.get("status", "QUESTION")
                
                if st.session_state.status == "READY":
                    st.success("✅ Datos auditados. Listo para guardar.")
                    time.sleep(1)
                    st.rerun()
        
        except Exception as e:
            st.error(f"Error en el motor de LAIA: {str(e)}")
    
    def _actualizar_borrador(self, nuevos_items):
        """Actualiza el borrador con nuevos items"""
        if not st.session_state.draft:
            st.session_state.draft = nuevos_items
        else:
            # Fusión inteligente
            dict_actual = {
                (i.get('serie') or i.get('modelo') or i.get('equipo')): i 
                for i in st.session_state.draft
            }
            
            for item in nuevos_items:
                key = item.get('serie') or item.get('modelo') or item.get('equipo')
                dict_actual[key] = item
            
            st.session_state.draft = list(dict_actual.values())
    
    def _mostrar_borrador(self):
        """Muestra la tabla del borrador y botones de acción"""
        st.divider()
        st.subheader("📊 Borrador de Movimientos")
        
        # Aplicar reglas de obsolescencia
        st.session_state.draft = self.stock_calc.aplicar_reglas_obsolescencia(
            st.session_state.draft
        )
        
        # Crear DataFrame
        df_editor = pd.DataFrame(st.session_state.draft)
        
        cols_base = [
            "categoria_item", "equipo", "marca", "modelo", "serie", 
            "cantidad", "estado", "tipo", "origen", "destino",
            "pasillo", "estante", "repisa", "guia", "fecha_llegada", 
            "ram", "disco", "procesador", "reporte"
        ]
        
        for c in cols_base:
            if c not in df_editor.columns:
                df_editor[c] = ""
        
        df_editor = df_editor.reindex(columns=cols_base).fillna("N/A")
        
        edited_df = st.data_editor(
            df_editor, 
            num_rows="dynamic", 
            use_container_width=True, 
            key="editor_v12"
        )
        
        if not df_editor.equals(edited_df):
            st.session_state.draft = edited_df.to_dict("records")
        
        # Botones GLPI
        self._mostrar_botones_glpi()
        
        # Botones de acción
        self._mostrar_botones_accion()
    
    def _mostrar_botones_glpi(self):
        """Muestra los botones de integración GLPI"""
        col_glpi1, col_glpi2 = st.columns([2, 1])
        
        with col_glpi1:
            if st.button("🔍 SOLICITAR BÚSQUEDA EN OFICINA"):
                serie_valida = next(
                    (item.get('serie') for item in st.session_state.draft 
                     if item.get('serie') and item.get('serie') != "N/A"), 
                    None
                )
                
                if serie_valida:
                    if self.github.solicitar_busqueda_glpi(serie_valida):
                        st.toast(f"Pedido enviado para serie {serie_valida}", icon="📡")
                        time.sleep(10)
                        st.rerun()
                else:
                    st.warning("⚠️ No hay una serie válida para buscar.")
        
        with col_glpi2:
            if st.button("🔄 REVISAR Y AUTORELLENAR"):
                res_glpi = self.github.revisar_respuesta_glpi()
                
                if res_glpi and res_glpi.get("estado") == "completado":
                    self._autorellenar_glpi(res_glpi)
                else:
                    st.info("⏳ Esperando que la PC de la oficina envíe la ficha técnica...")
    
    def _autorellenar_glpi(self, res_glpi):
        """Autorellena datos desde GLPI"""
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
    
    def _mostrar_botones_accion(self):
        """Muestra los botones de guardar y descartar"""
        c1, c2 = st.columns([1, 4])
        
        with c1:
            forzar = st.checkbox("🔓 Forzar")
        
        with c2:
            if st.session_state.status == "READY" or forzar:
                if st.button("🚀 GUARDAR EN HISTÓRICO", type="primary", use_container_width=True):
                    self._guardar_borrador()
            else:
                st.button("🚀 GUARDAR (BLOQUEADO)", disabled=True, use_container_width=True)
        
        if st.button("🗑️ Descartar Todo"):
            self._limpiar_sesion()
    
    def _guardar_borrador(self):
        """Guarda el borrador en el histórico"""
        # Aplicar reglas de obsolescencia
        st.session_state.draft = self.stock_calc.aplicar_reglas_obsolescencia(
            st.session_state.draft
        )
        
        # Sellar con fecha
        ahora = (
            datetime.datetime.now(datetime.timezone.utc) - 
            datetime.timedelta(hours=5)
        ).strftime("%Y-%m-%d %H:%M")
        
        for item in st.session_state.draft:
            item["fecha_registro"] = ahora
        
        # Guardar
        if self.github.guardar_borrador(st.session_state.draft):
            st.success("✅ ¡Guardado con éxito!")
            self._limpiar_sesion()
            time.sleep(1)
            st.rerun()
    
    def _limpiar_sesion(self):
        """Limpia la sesión"""
        st.session_state.draft = []
        st.session_state.messages = []
        st.session_state.status = "NEW"
        st.rerun()
