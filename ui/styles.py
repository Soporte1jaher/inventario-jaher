import streamlit as st

LOGO_URL = "https://raw.githubusercontent.com/Soporte1jaher/inventario-jaher/main/assets/logo_jaher.png"

def inject_css():
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.2rem; padding-bottom: 1.2rem; max-width: 1200px; }

        div[data-testid="stVerticalBlockBorderWrapper"]{
          border-radius: 16px !important;
          border: 1px solid rgba(255,255,255,0.08) !important;
          background: rgba(255,255,255,0.02);
        }

        .stButton button{
          border-radius: 12px !important;
          font-weight: 800 !important;
          padding: 0.55rem 0.9rem !important;
        }

        div[data-testid="stDataEditor"]{
          border-radius: 14px;
          overflow: hidden;
          border: 1px solid rgba(255,255,255,0.08);
        }

        /* Logo flotante */
        #jaher-logo{
          position: fixed;
          top: 14px;
          right: 18px;
          z-index: 9999;
          width: 120px;
          opacity: 0.95;
          filter: drop-shadow(0 6px 14px rgba(0,0,0,0.35));
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_logo():
    st.markdown(
        f"""<img id="jaher-logo" src="{LOGO_URL}" />""",
        unsafe_allow_html=True
    )
