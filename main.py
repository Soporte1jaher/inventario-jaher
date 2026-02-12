import os
import sys
import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ui.styles import inject_css, render_logo
from ui.chat_tab import ChatTab
from ui.stock_tab import StockTab
from ui.cleaning_tab import CleaningTab

st.set_page_config(page_title="LAIA v91.2", page_icon="🧠", layout="wide")

def main():
    inject_css()
    render_logo()

    tab1, tab2, tab3 = st.tabs(["💬 Chat Auditor", "📊 Stock Real", "🗑️ Limpieza"])

    with tab1:
        ChatTab().render()

    with tab2:
        StockTab().render()

    with tab3:
        CleaningTab().render()

if __name__ == "__main__":
    main()
