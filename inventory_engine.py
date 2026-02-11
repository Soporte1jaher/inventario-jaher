import pandas as pd

def extraer_gen(proc):
    if not proc or str(proc).strip().lower() in ['n/a', '', 'nan']: return 'moderno'
    p = str(proc).lower()
    obsoletos = ['4th', '5th', '6th', '7th', '8th', '9th', '4ta', '5ta', '6ta', '7ta', '8va', '9na', 'gen 8', 'gen 9']
    if any(x in p for x in obsoletos): return 'obsoleto'
    return 'moderno'

def calcular_stock_web(df):
    if df is None or df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    df_c = df.copy()
    df_c.columns = df_c.columns.str.lower().str.strip()
    df_c['cant_n'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(0)
    df_c['gen_cpu'] = df_c['procesador'].apply(extraer_gen)
    
    # ... (Pega aquí el resto de la lógica de filtros que tenías) ...
    return st_res, bod_res, danados_res, df_c
