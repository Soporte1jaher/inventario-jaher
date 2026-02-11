"""
ui/cleaning_tab.py
Interfaz del tab de limpieza inteligente
"""
import streamlit as st
from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler
from config.settings import Config

class CleaningTab:
    """Tab de limpieza inteligente del historial"""
    
    def __init__(self):
        self.ai_engine = AIEngine()
        self.github = GitHubHandler()
    
    def render(self):
        """Renderiza el tab completo"""
        st.subheader("🗑️ Limpieza Inteligente del Historial")
        
        st.markdown("""
        Usa este panel para eliminar registros específicos mediante lenguaje natural. 
        LAIA analizará el historial para encontrar coincidencias.
        """)
        
        st.info("💡 Ejemplos: 'Borra lo de Latacunga', 'Elimina la serie 89238928', 'Limpia los teclados de marca N/A'")
        
        txt_borrar = st.text_input(
            "¿Qué deseas eliminar?", 
            placeholder="Escribe tu instrucción aquí..."
        )
        
        if st.button("🔥 BUSCAR Y GENERAR ORDEN DE BORRADO", type="secondary"):
            if txt_borrar:
                self._procesar_orden_borrado(txt_borrar)
            else:
                st.warning("Escribe una instrucción antes de presionar el botón.")
    
    def _procesar_orden_borrado(self, instruccion):
        """Procesa la orden de borrado"""
        try:
            with st.spinner("LAIA analizando historial para identificar el objetivo..."):
                # Obtener contexto del historial
                hist = self.github.obtener_historico()
                
                # Últimos 40 registros para contexto
                contexto = hist[-40:] if hist else []
                
                # Generar orden con IA
                orden = self.ai_engine.generar_orden_borrado(instruccion, contexto)
                
                # Enviar orden al buzón
                if self.github.agregar_a_archivo(
                    Config.FILE_BUZON, 
                    orden, 
                    "Orden de Borrado Inteligente"
                ):
                    st.success("✅ Orden de borrado enviada con éxito.")
                    st.json(orden)
                    st.warning("⚠️ El Robot en tu PC procesará esto en unos segundos y actualizará el Excel y la Nube.")
                else:
                    st.error("❌ No se pudo enviar la orden a GitHub.")
        
        except Exception as e:
            st.error(f"Error en el motor de limpieza: {e}")
