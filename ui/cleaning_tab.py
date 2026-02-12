import streamlit as st
from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler

class CleaningTab:
    def __init__(self):
        self.ai_engine = AIEngine()
        self.github = GitHubHandler()

    def render(self):
        st.subheader("🗑️ Limpieza Inteligente del Historial")
        st.markdown("LAIA analizará el historial para encontrar qué registros borrar.")
        
        st.info("💡 Ejemplo: 'Borra lo de Latacunga' o 'Elimina la serie 12345'")
        
        txt_borrar = st.text_input("¿Qué deseas eliminar?", placeholder="Escribe aquí...", key="txt_limpieza")
        
        if st.button("🔥 BUSCAR Y GENERAR ORDEN DE BORRADO", type="secondary"):
            if txt_borrar:
                self._procesar_orden_borrado(txt_borrar)
            else:
                st.warning("Escribe una instrucción primero.")

    def _procesar_orden_borrado(self, instruccion):
        try:
            with st.spinner("LAIA analizando historial..."):
                # 1. Obtener historial
                hist = self.github.obtener_historico()
                
                # Si es None, es un error de conexión/token
                if hist is None:
                    st.error("❌ Error de comunicación con GitHub. Revisa el Token en los Secrets de la Web.")
                    return
                
                # Si es una lista vacía, no hay nada que borrar
                if len(hist) == 0:
                    st.warning("⚠️ El historial ya está vacío. No hay nada que borrar.")
                    return

                # 2. Si hay datos, proceder con la IA
                contexto = hist[-40:]
                orden = self.ai_engine.generar_orden_borrado(instruccion, contexto)
                
                if orden:
                    if self.github.enviar_orden_limpieza(orden):
                        st.success("✅ Orden enviada con éxito.")
                        st.json(orden)
                    else:
                        st.error("❌ No se pudo enviar la orden.")
        except Exception as e:
            st.error(f"Error en limpieza: {e}")
