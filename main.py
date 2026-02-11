import os
import sys

# 🔥 Forzar root del proyecto al PYTHONPATH
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import streamlit as st
from config.settings import CUSTOM_CSS
from ui.chat_tab import ChatTab
from ui.stock_tab import StockTab
from ui.cleaning_tab import CleaningTab

# ==========================================
# CONFIGURACIÓN INICIAL
# ==========================================
st.set_page_config(
    page_title="LAIA v91.2 - Auditora Senior",
    page_icon="🧠",
    layout="wide"
)

# Aplicar estilos CSS
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================
def main():
    """Función principal de la aplicación"""
    
    # Crear tabs
    tab1, tab2, tab3 = st.tabs([
        "💬 Chat Auditor",
        "📊 Stock Real",
        "🗑️ Limpieza"
    ])
    
    # Renderizar cada tab
    with tab1:
        chat = ChatTab()
        chat.render()
    
    with tab2:
        stock = StockTab()
        stock.render()
    
    with tab3:
        cleaning = CleaningTab()
        cleaning.render()

if __name__ == "__main__":
    main()
