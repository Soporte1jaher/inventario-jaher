import pandas as pd
from hardware_utils import extraer_gen

def calcular_stock_web(df):
    if df is None or df.empty: 
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    df_c = df.copy()
    df_c.columns = df_c.columns.str.lower().str.strip()
    
    for col in df_c.columns:
        df_c[col] = df_c[col].astype(str).str.lower().str.strip()
    
    df_c['cant_n'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(0)
    df_c['gen_cpu'] = df_c['procesador'].apply(extraer_gen)

    perifericos_list = ['mouse', 'teclado', 'cable', 'hdmi', 'limpiador', 'cargador', 'toner', 'tinta', 'parlante', 'herramienta']
    
    es_periferico = df_c['equipo'].str.contains('|'.join(perifericos_list), na=False)
    es_dañado = df_c['estado'].str.contains('dañado|obsoleto|chatarrización', na=False)
    es_destino_bodega = df_c['destino'] == 'bodega'

    # 1. STOCK PERIFÉRICOS
    df_p = df_c[es_periferico].copy()
    if not df_p.empty:
        def procesar_saldo(row):
            t = row['tipo']
            if any(x in t for x in ['recibido', 'ingreso', 'entrada', 'llegó']): return row['cant_n']
            if any(x in t for x in ['enviado', 'salida', 'despacho', 'egreso', 'envio']): return -row['cant_n']
            return 0
        df_p['val'] = df_p.apply(procesar_saldo, axis=1)
        st_res = (df_p.groupby(['equipo', 'marca', 'modelo']).agg({'val': 'sum'}).reset_index())
        st_res = st_res[st_res['val'] > 0]
    else:
        st_res = pd.DataFrame(columns=['equipo', 'marca', 'modelo', 'val'])

    # 2. BODEGA (Equipos Modernos)
    bod_res = df_c[es_destino_bodega & ~es_periferico & ~es_dañado & (df_c['gen_cpu'] == 'moderno')].copy()

    # 3. DAÑADOS / OBSOLETOS
    danados_res = df_c[es_dañado | (df_c['gen_cpu'] == 'obsoleto')].copy()

    return st_res, bod_res, danados_res, df_c
