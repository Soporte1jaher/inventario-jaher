"""
ui/cleaning_tab.py - CORREGIDO
"""
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
        st.markdown("LAIA analizará el historial para encontrar qué registros borrar según tu instrucción.")
        
        st.info("💡 Ejemplo: 'Borra lo de Latacunga' o 'Elimina la serie 12345'")
        
        txt_borrar = st.text_input("¿Qué deseas eliminar?", placeholder="Escribe aquí...")
        
        if st.button("🔥 BUSCAR Y GENERAR ORDEN DE BORRADO", type="secondary"):
            if txt_borrar:
                self._procesar_orden_borrado(txt_borrar)
            else:
                st.warning("Escribe una instrucción primero.")
   
       def _procesar_orden_borrado(self, instruccion):
        try:
            with st.spinner("LAIA analizando historial..."):
                # 1. Obtener historial (Usando el método nuevo)
                hist = self.github.obtener_historico()
                contexto_breve = hist[-40:] if hist else []
                 
                # 2. Generar orden con IA
                orden = self.ai_engine.generar_orden_borrado(instruccion, contexto_breve)
                 
                if orden:
                    # 3. Enviar al buzón (Usando la lógica de APPEND del original)
                    if self.github.enviar_orden_limpieza(orden):
                        st.success("✅ Orden de borrado enviada con éxito.")
                        st.json(orden)
                        st.warning("⚠️ El Robot en tu PC procesará esto en unos segundos.")
                    else:
                        st.error("❌ No se pudo enviar la orden a GitHub.")
                else:
                    st.error("LAIA no pudo interpretar la orden.")
        except Exception as e:
            st.error(f"Error en limpieza: {e}")
