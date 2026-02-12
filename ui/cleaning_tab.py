"""
ui/cleaning_tab.py
Interfaz del tab de limpieza inteligente
"""
import streamlit as st
import json
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
        """Procesa la orden de borrado exactamente como el original"""
        try:
            with st.spinner("LAIA analizando historial para identificar el objetivo..."):
                # 1. Obtener historial (el original devolvía data, sha)
                # Asumimos que tu handler nuevo ya devuelve solo la lista o []
                hist = self.github.obtener_archivo(Config.FILE_HISTORICO)
                
                if not hist:
                    st.error("No hay historial disponible para analizar.")
                    return

                # 2. Preparar contexto (últimos 40 registros como en el original)
                contexto_breve = hist[-40:]
                
                # 3. Llamar a la IA con la lógica de "DBA Senior"
                orden = self.ai_engine.generar_orden_borrado(instruccion, contexto_breve)
                
                if orden:
                    # 4. Enviar la orden al buzón para el Robot
                    # Importante: agregar_a_archivo debe hacer un "APPEND" (enviar_github original)
                    if self.github.agregar_a_archivo(
                        Config.FILE_BUZON, 
                        orden, 
                        "Orden de Borrado Inteligente"
                    ):
                        st.success("✅ Orden de borrado enviada con éxito.")
                        st.json(orden)
                        st.warning("⚠️ El Robot en tu PC procesará esto en unos segundos.")
                    else:
                        st.error("❌ No se pudo enviar la orden a GitHub.")
                else:
                    st.error("LAIA no pudo interpretar la orden de borrado.")
        
        except Exception as e:
            st.error(f"Error en el motor de limpieza: {e}")
