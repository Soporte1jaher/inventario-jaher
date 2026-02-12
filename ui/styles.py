import streamlit as st

LOGO_URL = "https://raw.githubusercontent.com/Soporte1jaher/inventario-jaher/main/assets/logo_jaher.png"

def inject_css():
    st.markdown(
        """
        <style>
        /* ====== CORPORATIVO JAHER ====== */
        .block-container { padding-top: 1.2rem; }

        /* Tarjetas / secciones con borde suave */
        div[data-testid="stVerticalBlockBorderWrapper"]{
            border-radius: 16px;
        }

        /* Botones */
        .stButton > button {
            border-radius: 12px !important;
            padding: 0.55rem 0.9rem !important;
            font-weight: 700 !important;
        }

        /* Data editor */
        div[data-testid="stDataEditor"]{
            border-radius: 14px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.08);
        }

        /* Tabs más “pro” */
        button[role="tab"]{
            border-radius: 12px 12px 0 0 !important;
            padding: 0.6rem 0.9rem !important;
            font-weight: 800 !important;
        }

        /* Alerts */
        div[data-testid="stAlert"]{
            border-radius: 14px;
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
          filter: drop-shadow(0 6px 18px rgba(0,0,0,0.35));
          pointer-events: none;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

def render_logo():
    st.markdown(
        f"""<img id="jaher-logo" src="{LOGO_URL}" />""",
        unsafe_allow_html=True
    )
