import pandas as pd

def extraer_gen(proc):
    if not proc:
        return "moderno"

    p = str(proc).lower()

    if any(x in p for x in ['4th','5th','6th','7th','8th','9th','8va','9na']):
        return "obsoleto"

    if any(x in p for x in ['10th','11th','12th','13th','14th','10ma']):
        return "moderno"

    return "moderno"

def calcular_stock_web(df):
    if df is None or df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df_c = df.copy()
    df_c.columns = df_c.columns.str.lower().str.strip()

    df_c["cant_n"] = pd.to_numeric(df_c["cantidad"], errors="coerce").fillna(0)
    df_c["gen_cpu"] = df_c["procesador"].apply(extraer_gen)

    es_dañado = df_c["estado"].str.contains("dañado|obsoleto|chatarrización", na=False)
    es_bodega = df_c["destino"] == "bodega"

    st_res = df_c.groupby(["equipo"]).agg({"cant_n":"sum"}).reset_index()
    bod_res = df_c[es_bodega & (df_c["gen_cpu"]=="moderno")]
    danados_res = df_c[es_dañado | (df_c["gen_cpu"]=="obsoleto")]

    return st_res, bod_res, danados_res, df_c
