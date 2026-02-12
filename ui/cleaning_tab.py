import streamlit as st
from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler
from config.settings import Config

class CleaningTab:
    def __init__(self):
        self.ai_engine = AIEngine()
        self.github = GitHubHandler()

    def render(self):
        st.subheader("🗑️ Limpieza Inteligente del Historial")
        st.markdown("""
        Usa este panel para eliminar registros específicos mediante lenguaje natural. 
        LAIA analizará el historial para encontrar coincidencias.
        """)
        
        st.info("💡 Ejemplos: 'Borra lo de Latacunga', 'Elimina la serie 89238928'")
        
        txt_borrar = st.text_input(
            "¿Qué deseas eliminar?", 
            placeholder="Escribe tu instrucción aquí...",
            key="input_limpieza"
        )
        
        if st.button("🔥 BUSCAR Y GENERAR ORDEN DE BORRADO", type="secondary"):
            if txt_borrar:
                self._procesar_orden_borrado(txt_borrar)
            else:
                st.warning("Escribe una instrucción antes de presionar el botón.")

    def _procesar_orden_borrado(self, instruccion):
        try:
            with st.spinner("LAIA analizando historial..."):
                # 1. Obtener historial
                hist = self.github.obtener_historico()
                if not hist:
                    st.error("No hay historial disponible.")
                    return

                # 2. Contexto para la IA
                contexto = hist[-40:]
                
                # 3. Generar orden
                orden = self.ai_engine.generar_orden_borrado(instruccion, contexto)
                
                if orden:
                    # 4. Enviar orden (Usando enviar_orden_limpieza que definimos en github_handler)
                    if self.github.enviar_orden_limpieza(orden):
                        st.success("✅ Orden de borrado enviada con éxito.")
                        st.json(orden)
                        st.warning("⚠️ El Robot en tu PC procesará esto en unos segundos.")
                    else:
                        st.error("❌ No se pudo enviar a GitHub.")
                else:
                    st.error("LAIA no pudo interpretar la orden.")
        except Exception as e:
            st.error(f"Error en el motor de limpieza: {e}")
