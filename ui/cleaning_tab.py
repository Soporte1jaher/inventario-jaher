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
                # 1. Obtener historial real para dar contexto a la IA
                hist = self.github.obtener_historico()
                if not hist:
                    st.error("El historial está vacío o no se pudo leer.")
                    return

                # 2. Tomar muestra para la IA (los últimos 40 registros)
                contexto = hist[-40:]
                
                # 3. Pedir a la IA que genere el JSON de borrado (formato DBA Senior)
                orden = self.ai_engine.generar_orden_borrado(instruccion, contexto)
                
                if orden:
                    # 4. ENVIAR AL BUZÓN (MODO DIRECTO)
                    # Usamos enviar_archivo_directo para que el archivo sea un {objeto} 
                    # y NO una lista [objetos] que confunda al Robot.
                    if self.github.enviar_archivo_directo("buzon.json", orden, "Orden de Borrado Inteligente"):
                        st.success("✅ Orden enviada con éxito.")
                        st.json(orden)
                        st.warning("⚠️ El Robot en tu PC procesará esto en unos segundos.")
                    else:
                        st.error("❌ No se pudo conectar con GitHub.")
                else:
                    st.error("LAIA no pudo identificar qué registros borrar.")
        except Exception as e:
            st.error(f"Error en limpieza: {e}")
