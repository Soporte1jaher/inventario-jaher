import os
import sys
import streamlit as st

# Forzar root
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ui.chat_tab import ChatTab
from ui.stock_tab import StockTab
from ui.cleaning_tab import CleaningTab

st.set_page_config(page_title="LAIA v91.2", page_icon="🧠", layout="wide")


def inject_css():
    st.markdown("""
    <style>
    /* Fondo general (más PRO) */
    .stApp {
        background: radial-gradient(circle at top, #111827 0%, #0b1220 45%, #070b14 100%);
    }

    /* Quitar padding feo arriba */
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }

    /* Tabs más bonitas */
    button[data-baseweb="tab"] {
        font-size: 15px !important;
        padding: 10px 16px !important;
        border-radius: 12px !important;
        margin-right: 6px !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background: rgba(16,185,129,0.14) !important;
        border: 1px solid rgba(16,185,129,0.35) !important;
    }

    /* Chat input (la barra gigante) */
    div[data-testid="stChatInput"] textarea {
        border-radius: 14px !important;
        border: 1px solid rgba(148,163,184,0.25) !important;
        background: rgba(15,23,42,0.78) !important;
        padding: 12px 14px !important;
        font-size: 15px !important;
        min-height: 52px !important;
    }
    div[data-testid="stChatInput"] textarea:focus {
        border: 1px solid rgba(16,185,129,0.75) !important;
        box-shadow: 0 0 0 4px rgba(16,185,129,0.12) !important;
    }

    /* Botón enviar */
    div[data-testid="stChatInput"] button {
        border-radius: 12px !important;
        background: rgba(16,185,129,0.12) !important;
        border: 1px solid rgba(16,185,129,0.35) !important;
    }
    div[data-testid="stChatInput"] button:hover {
        background: rgba(16,185,129,0.22) !important;
    }

    /* Mensajes tipo tarjeta */
    div[data-testid="stChatMessage"] {
        background: rgba(15,23,42,0.55) !important;
        border: 1px solid rgba(148,163,184,0.18) !important;
        border-radius: 16px !important;
        padding: 14px 14px !important;
        margin-bottom: 10px !important;
        box-shadow: 0 8px 24px rgba(0,0,0,0.25) !important;
    }

    /* Sidebar (si aparece) más suave */
    section[data-testid="stSidebar"] {
        background: rgba(10,14,26,0.85) !important;
        border-right: 1px solid rgba(148,163,184,0.12) !important;
    }
    </style>
    """, unsafe_allow_html=True)


def main():
    inject_css()  # <-- SOLO ESTO y ya cambia todo lo visual

    tab1, tab2, tab3 = st.tabs(["💬 Chat Auditor", "📊 Stock Real", "🗑️ Limpieza"])

    with tab1:
        ChatTab().render()

    with tab2:
        StockTab().render()

    with tab3:
        CleaningTab().render()


if __name__ == "__main__":
    main()
